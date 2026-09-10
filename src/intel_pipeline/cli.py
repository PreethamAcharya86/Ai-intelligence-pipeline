from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path

from .collectors import collect_arxiv, collect_rss_signals, enrich_paper_github, import_entities
from .export import write_bundle
from .http import AsyncHttpClient, FetchPolicy
from .models import utc_now
from .resolution import DEFAULT_CANONICAL_ENTITIES, EntityResolver
from .storage import StateStore


def load_config(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


async def run(args: argparse.Namespace) -> dict[str, int]:
    config = load_config(args.config)
    store = StateStore(args.state_db)
    resolver = EntityResolver(DEFAULT_CANONICAL_ENTITIES, store)
    startups, products = [], []
    for feed in config.get("startup_feeds", []):
        startups.extend(import_entities(feed["path"], "startup", feed["name"]))
    for feed in config.get("product_feeds", []):
        products.extend(import_entities(feed["path"], "product", feed["name"]))
    for record in startups:
        record.entity_name = resolver.resolve(record.entity_name).canonical_name
    for record in products:
        record.startup_name = resolver.resolve(record.startup_name).canonical_name

    async with AsyncHttpClient(FetchPolicy(concurrency=args.concurrency, per_host=args.per_host)) as client:
        papers_task = collect_arxiv(client, args.paper_limit)
        news_task = collect_rss_signals(client, store, config.get("news_rss", []), "NEWS")
        jobs_task = collect_rss_signals(client, store, config.get("job_rss", []), "JOB")
        papers_result, news_result, jobs_result = await asyncio.gather(
            papers_task, news_task, jobs_task, return_exceptions=True
        )
        if isinstance(papers_result, Exception):
            store.log(utc_now(), "arXiv", "failed", detail=str(papers_result))
            logging.error("arXiv collection failed; continuing with remaining sources: %s", papers_result)
            papers = []
        else:
            papers = papers_result
        # RSS collectors intentionally isolate their own feed failures; this guard keeps a future
        # collector implementation from turning a partial run into a failed export.
        news = [] if isinstance(news_result, Exception) else news_result
        jobs = [] if isinstance(jobs_result, Exception) else jobs_result
        if isinstance(news_result, Exception):
            store.log(utc_now(), "news", "failed", detail=str(news_result))
        if isinstance(jobs_result, Exception):
            store.log(utc_now(), "jobs", "failed", detail=str(jobs_result))
        if args.enrich_github:
            await enrich_paper_github(client, papers)

    tables = {
        "startups": [record.row() for record in startups],
        "products": [record.row() for record in products],
        "research_papers": [record.row() for record in papers],
        "jobs": [record.row() for record in jobs],
        "news": [record.row() for record in news],
        "entity_mapping_log": store.mapping_rows(),
    }
    counts = write_bundle(args.output_dir, tables)
    logging.info("Export complete: %s", counts)
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the source-traceable FrontierAtlas ingestion pipeline")
    parser.add_argument("--config", default="config/sources.example.json")
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--state-db", default="data/state/pipeline.sqlite3")
    parser.add_argument("--paper-limit", type=int, default=1000)
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--per-host", type=int, default=4)
    parser.add_argument("--enrich-github", action="store_true", help="Attempt Papers with Code/GitHub enrichment for papers")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
