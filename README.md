# FrontierAtlas / GraphOne Intelligence Ingestion

A source-traceable, asynchronous data ingestion project built for the AI Engineer trial. It deliberately never fabricates records: a record is emitted only when it has an originating URL, and the LLM layer is instructed to extract only source-supported facts.

## What is implemented

- Bounded async HTTP crawler with global/per-host concurrency, timeout protection, exponential backoff and jitter for 429/5xx responses.
- arXiv pagination for up to 1,000 research papers (or a configured higher limit), plus optional Papers with Code -> GitHub live-star enrichment.
- RSS/Atom ingestion from five news feeds and configurable job feeds; fetched pages are converted to readable full text and passed through a strict 24-hour UTC freshness gate.
- Durable SQLite URL ledger prevents duplicate processing across repeated runs; its schema maps directly to a Postgres `UNIQUE(url_hash)` ledger for distributed deployment.
- Imported startup/product directory exports require a valid source URL per row. No “demo” or LLM-created entities are included.
- Deterministic entity resolver: normalized exact match first, then thresholded fuzzy matching against a 50-entity seed list; every decision is exported.
- LLM orchestration primitives for semantic chunking, provider fallback (Gemini Flash -> Groq Llama -> DeepSeek when configured), and jittered 429 handling.
- CSV bundle with six Google-Sheets-ready tabs: Startups, Products, Research Papers, Jobs, News, Entity Mapping Log.

## Run it

Requires Python 3.11+. Create an isolated environment, install, then copy the source configuration:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
Copy-Item config/sources.example.json config/sources.json
frontier-ingest --config config/sources.json --paper-limit 1000 --enrich-github
```

Output is written to `output/`. Create a Google Sheet with the six named tabs and import each matching CSV. The pipeline does not publish a public sheet automatically because that requires an explicitly authorized Google service account and sharing target.

For startup and product counts, provide approved directory exports in `data/incoming/` as documented in [data/incoming/README.md](data/incoming/README.md). This is intentional: it keeps every submitted row auditable and avoids data invented to satisfy row quotas.

## Commands and verification

```powershell
python -m pytest -q
frontier-ingest --help
```

The live run is safe to repeat: previously seen news/job URLs remain in `data/state/pipeline.sqlite3`. To re-ingest a signal deliberately, use a new state database path rather than deleting the current ledger.

## Design notes

`architecture.pdf` contains the scale, rate-limit, freshness, storage, and anti-bot strategy required by the assignment. The local implementation is an intentionally small execution slice: scale it by publishing source discovery jobs to a queue, horizontally autoscaling workers, and replacing SQLite with Postgres/object storage as described in the document.

## Responsible collection

The collector is designed for permitted APIs, RSS feeds, and approved directory exports. It uses per-domain rate limits, does not attempt CAPTCHA circumvention, and documents a compliant browser/API escalation path for JavaScript-heavy or protected sources. Review each source’s terms, robots policy, and API contract before enabling it in production.