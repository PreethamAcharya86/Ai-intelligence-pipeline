from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable


TABLES = ("startups", "products", "research_papers", "jobs", "news", "entity_mapping_log")


def write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields or ["empty"])
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def write_bundle(output_dir: str | Path, tables: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
    destination = Path(output_dir)
    counts = {name: write_csv(destination / f"{name}.csv", tables.get(name, [])) for name in TABLES}
    (destination / "manifest.json").write_text(json.dumps({"counts": counts, "format": "CSV suitable for one Google Sheet tab per file"}, indent=2), encoding="utf-8")
    return counts
