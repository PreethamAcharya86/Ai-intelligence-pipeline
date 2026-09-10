from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class StateStore:
    """SQLite is the durable per-worker state; promote this schema to Postgres at scale."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _initialize(self) -> None:
        with self.connection() as conn:
            conn.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS seen_urls (
                    url_hash TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    content_hash TEXT
                );
                CREATE TABLE IF NOT EXISTS entity_mapping (
                    raw_name TEXT NOT NULL,
                    canonical_name TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    method TEXT NOT NULL,
                    mapped_at TEXT NOT NULL,
                    PRIMARY KEY(raw_name, canonical_name)
                );
                CREATE TABLE IF NOT EXISTS crawl_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    occurred_at TEXT NOT NULL,
                    source TEXT NOT NULL,
                    url TEXT,
                    status TEXT NOT NULL,
                    detail TEXT
                );
            """)

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256(value.strip().encode("utf-8")).hexdigest()

    def was_seen(self, url: str) -> bool:
        with self.connection() as conn:
            return conn.execute("SELECT 1 FROM seen_urls WHERE url_hash = ?", (self._hash(url),)).fetchone() is not None

    def mark_seen(self, url: str, kind: str, occurred_at: str, content: str = "") -> None:
        with self.connection() as conn:
            conn.execute("INSERT OR IGNORE INTO seen_urls(url_hash,url,kind,first_seen_at,content_hash) VALUES (?,?,?,?,?)",
                         (self._hash(url), url, kind, occurred_at, self._hash(content) if content else None))

    def log(self, occurred_at: str, source: str, status: str, url: str | None = None, detail: str | None = None) -> None:
        with self.connection() as conn:
            conn.execute("INSERT INTO crawl_events(occurred_at,source,url,status,detail) VALUES (?,?,?,?,?)",
                         (occurred_at, source, url, status, detail))

    def save_mapping(self, raw: str, canonical: str, confidence: float, method: str, mapped_at: str) -> None:
        with self.connection() as conn:
            conn.execute("INSERT OR REPLACE INTO entity_mapping VALUES (?,?,?,?,?)", (raw, canonical, confidence, method, mapped_at))

    def mapping_rows(self) -> list[dict[str, object]]:
        with self.connection() as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM entity_mapping ORDER BY mapped_at DESC")]

    def event_rows(self) -> list[dict[str, object]]:
        with self.connection() as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM crawl_events ORDER BY id DESC")]
