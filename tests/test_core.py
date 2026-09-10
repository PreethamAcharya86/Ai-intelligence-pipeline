from datetime import datetime, timezone

from intel_pipeline.freshness import is_fresh, parse_published
from intel_pipeline.llm import semantic_chunks
from intel_pipeline.resolution import EntityResolver
from intel_pipeline.storage import StateStore
from intel_pipeline.export import write_bundle


def test_relative_date_is_normalized() -> None:
    now = datetime(2026, 8, 1, 12, tzinfo=timezone.utc)
    assert parse_published("2 hours ago", now) == datetime(2026, 8, 1, 10, tzinfo=timezone.utc)
    assert is_fresh(parse_published("25 hours ago", now), now=now) is False


def test_chunking_stays_under_limit() -> None:
    chunks = semantic_chunks("Sentence. " * 100, max_chars=70)
    assert len(chunks) > 1
    assert all(len(chunk) <= 70 for chunk in chunks)


def test_resolution_and_mapping_are_durable(tmp_path) -> None:
    store = StateStore(tmp_path / "state.db")
    result = EntityResolver(["OpenAI"], store).resolve("OpenAI, Inc.")
    assert result.canonical_name == "OpenAI"
    assert store.mapping_rows()[0]["method"] == "normalized_exact"


def test_export_always_writes_six_google_sheet_tabs(tmp_path) -> None:
    counts = write_bundle(tmp_path, {"news": [{"content.title": "A source-backed title"}]})
    assert counts["news"] == 1
    assert all((tmp_path / f"{name}.csv").exists() for name in counts)
