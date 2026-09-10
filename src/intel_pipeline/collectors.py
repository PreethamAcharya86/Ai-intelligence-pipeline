from __future__ import annotations

import asyncio
import csv
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from bs4 import BeautifulSoup

from .freshness import is_fresh, iso, parse_published
from .http import AsyncHttpClient, FetchError
from .models import Product, ResearchPaper, Signal, Source, Startup, utc_now
from .storage import StateStore

ATOM = {"atom": "http://www.w3.org/2005/Atom"}
GITHUB_URL = re.compile(r"https?://github\.com/[\w.-]+/[\w.-]+", re.I)


async def collect_arxiv(client: AsyncHttpClient, limit: int, query: str = "cat:cs.AI OR cat:cs.CL OR cat:cs.LG") -> list[ResearchPaper]:
    """Fetch arXiv in pages; no invented repository links or metrics."""
    page_size, records = 100, []
    urls = [f"https://export.arxiv.org/api/query?search_query={query.replace(' ', '%20')}&start={start}&max_results={min(page_size, limit-start)}&sortBy=submittedDate&sortOrder=descending"
            for start in range(0, limit, page_size)]
    for url in urls:
        text = await client.get_text(url, accept="application/atom+xml")
        root = ET.fromstring(text)
        for entry in root.findall("atom:entry", ATOM):
            identifier = (entry.findtext("atom:id", namespaces=ATOM) or "").strip()
            published = parse_published(entry.findtext("atom:published", namespaces=ATOM))
            if not identifier or not published:
                continue
            records.append(ResearchPaper(
                source=Source("arXiv", identifier), title=" ".join((entry.findtext("atom:title", namespaces=ATOM) or "").split()),
                authors=[author.findtext("atom:name", namespaces=ATOM) or "" for author in entry.findall("atom:author", ATOM)],
                paper_url=identifier, published_date=iso(published)))
    return records[:limit]


async def enrich_paper_github(client: AsyncHttpClient, papers: list[ResearchPaper], github_token: str | None = None) -> None:
    """Attempts a legitimate Papers with Code page lookup, then reads GitHub's live star count."""
    headers_token_note = "" if github_token else " (unauthenticated GitHub API quota)"
    async def one(paper: ResearchPaper) -> None:
        try:
            # PWC slug lookup is intentionally optional: failure retains valid arXiv record.
            slug = re.sub(r"[^a-z0-9]+", "-", paper.title.lower()).strip("-")
            html = await client.get_text(f"https://paperswithcode.com/paper/{slug}")
            match = GITHUB_URL.search(html)
            if not match:
                return
            paper.github_url = match.group(0).rstrip(".,)")
            owner_repo = paper.github_url.split("github.com/", 1)[1].split("/")[:2]
            api_url = f"https://api.github.com/repos/{'/'.join(owner_repo)}"
            # Client uses fixed headers; a token is intentionally not logged or persisted.
            repo = json.loads(await client.get_text(api_url, accept="application/vnd.github+json"))
            paper.github_stars = int(repo.get("stargazers_count", 0))
        except (FetchError, json.JSONDecodeError, IndexError):
            return
    await asyncio.gather(*(one(paper) for paper in papers))


def _rss_entries(xml_text: str) -> Iterable[dict[str, str]]:
    root = ET.fromstring(xml_text)
    for item in root.findall(".//item"):
        yield {"title": item.findtext("title") or "", "url": item.findtext("link") or "",
               "date": item.findtext("pubDate") or item.findtext("published") or "",
               "description": item.findtext("description") or ""}
    for entry in root.findall(".//{http://www.w3.org/2005/Atom}entry"):
        link = entry.find("{http://www.w3.org/2005/Atom}link")
        yield {"title": entry.findtext("{http://www.w3.org/2005/Atom}title") or "",
               "url": (link.attrib.get("href", "") if link is not None else ""),
               "date": entry.findtext("{http://www.w3.org/2005/Atom}published") or entry.findtext("{http://www.w3.org/2005/Atom}updated") or "",
               "description": entry.findtext("{http://www.w3.org/2005/Atom}summary") or ""}


async def _full_text(client: AsyncHttpClient, url: str, fallback: str) -> str:
    try:
        soup = BeautifulSoup(await client.get_text(url), "html.parser")
        for noise in soup(["script", "style", "nav", "footer", "header", "aside"]):
            noise.decompose()
        text = " ".join((soup.find("article") or soup.find("main") or soup).stripped_strings)
        return text[:80_000] or BeautifulSoup(fallback, "html.parser").get_text(" ", strip=True)
    except FetchError:
        return BeautifulSoup(fallback, "html.parser").get_text(" ", strip=True)


async def collect_rss_signals(client: AsyncHttpClient, store: StateStore, feeds: list[dict[str, str]], kind: str) -> list[Signal]:
    async def feed_records(feed: dict[str, str]) -> list[Signal]:
        try:
            xml_text = await client.get_text(feed["url"], accept="application/rss+xml,application/atom+xml,text/xml;q=0.9,*/*;q=0.8")
            result: list[Signal] = []
            for entry in _rss_entries(xml_text):
                published = parse_published(entry["date"])
                if not entry["url"] or not is_fresh(published) or store.was_seen(entry["url"]):
                    continue
                title = BeautifulSoup(entry["title"], "html.parser").get_text(" ", strip=True)
                full_text = await _full_text(client, entry["url"], entry["description"])
                lower = f"{title} {full_text}".lower()
                signal = Signal(kind=kind, source=Source(feed["name"], feed["url"]), title=title, url=entry["url"],
                                published_at=iso(published), full_text=full_text,
                                company=(title.split(" - ", 1)[0] if kind == "JOB" else None),
                                is_remote=("remote" in lower if kind == "JOB" else None),
                                role_family=("Engineering" if any(x in lower for x in ["engineer", "developer", "ml"]) else "Other") if kind == "JOB" else None)
                store.mark_seen(signal.url, kind, utc_now(), signal.full_text)
                result.append(signal)
            store.log(utc_now(), feed["name"], "ok", feed["url"], f"{len(result)} fresh {kind.lower()} records")
            return result
        except (FetchError, ET.ParseError, KeyError) as error:
            store.log(utc_now(), feed.get("name", "unknown"), "failed", feed.get("url"), str(error))
            return []
    nested = await asyncio.gather(*(feed_records(feed) for feed in feeds))
    return [record for group in nested for record in group]


def import_entities(path: str | Path, kind: str, source_name: str) -> list[Startup | Product]:
    """Validates local exports; every imported record retains its source URL."""
    path = Path(path)
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    if path.suffix.lower() == ".jsonl":
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    elif path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
    else:
        raise ValueError(f"Unsupported import format: {path.suffix}")
    output: list[Startup | Product] = []
    for row in rows:
        url = str(row.get("sourceUrl", "")).strip()
        if not url.startswith(("https://", "http://")):
            continue
        source = Source(source_name, url)
        if kind == "startup" and row.get("entityName"):
            count = row.get("employeeCount")
            output.append(Startup(source, str(row["entityName"]), str(row.get("description", "")), int(count) if str(count).isdigit() else None))
        if kind == "product" and row.get("startupName") and row.get("productName"):
            pricing = str(row.get("pricingModel", "UNKNOWN")).upper()
            output.append(Product(source, str(row["startupName"]), str(row["productName"]), pricing if pricing in {"FREE", "FREEMIUM", "PAID", "ENTERPRISE"} else "UNKNOWN"))
    return output
