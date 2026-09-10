from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "architecture.pdf"


def p(text, style):
    return Paragraph(text, style)


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#D8E2EE"))
    canvas.line(0.65 * inch, 0.55 * inch, 7.85 * inch, 0.55 * inch)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#637083"))
    canvas.drawString(0.65 * inch, 0.35 * inch, "FrontierAtlas Intelligence Ingestion - Technical Architecture")
    canvas.drawRightString(7.85 * inch, 0.35 * inch, f"Page {doc.page}")
    canvas.restoreState()


def main():
    doc = SimpleDocTemplate(str(OUT), pagesize=letter, rightMargin=.65*inch, leftMargin=.65*inch,
                            topMargin=.62*inch, bottomMargin=.72*inch)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("Title", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=22,
                           leading=26, textColor=colors.HexColor("#13233A"), spaceAfter=7)
    subtitle = ParagraphStyle("Subtitle", parent=styles["Normal"], fontSize=10.5, leading=14,
                              textColor=colors.HexColor("#526277"), spaceAfter=15)
    h = ParagraphStyle("H", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=13,
                       leading=16, textColor=colors.HexColor("#0A627A"), spaceBefore=8, spaceAfter=5)
    body = ParagraphStyle("Body", parent=styles["BodyText"], fontSize=9.2, leading=12.2,
                          textColor=colors.HexColor("#25354A"), alignment=TA_LEFT, spaceAfter=5)
    small = ParagraphStyle("Small", parent=body, fontSize=8.2, leading=10.3, spaceAfter=3)
    bullet = ParagraphStyle("Bullet", parent=body, leftIndent=12, firstLineIndent=-8, bulletIndent=0, spaceAfter=3)
    story = []
    story += [p("FrontierAtlas Intelligence Ingestion", title),
              p("Production architecture for source-traceable AI ecosystem data | August 2026", subtitle)]
    story += [p("Objective", h), p("Collect startups, products, research papers, jobs, and news as verifiable graph-ready records. The design prioritizes provenance and repeatability: no record may be emitted without a legitimate source URL; language models may structure evidence but may not invent facts.", body)]
    story += [p("1. Scale strategy - 500,000+ entity records", h)]
    rows = [
        [p("Layer", small), p("Design", small), p("Scale mechanism", small)],
        [p("Discovery", small), p("Scheduled API/RSS/directory enumerators emit immutable URL discovery events.", small), p("Partition by source + cursor/range; queue absorbs burst traffic.", small)],
        [p("Fetch", small), p("Stateless async workers enforce global and per-domain token buckets; raw HTML/PDF goes to object storage.", small), p("Autoscale workers on queue lag; use source-specific concurrency caps.", small)],
        [p("Transform", small), p("Schema validators, deterministic parsers, GitHub metric enrichers, and LLM extraction jobs consume raw snapshots.", small), p("Idempotency key = normalized URL + content hash + schema version.", small)],
        [p("Serve", small), p("Postgres holds canonical entities/provenance; graph/vector indexes are derived views.", small), p("Bulk upsert and append-only event history avoid cross-worker conflicts.", small)],
    ]
    table = Table(rows, colWidths=[.92*inch, 3.38*inch, 2.25*inch], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#E6F3F6")), ("TEXTCOLOR", (0,0), (-1,0), colors.HexColor("#0A5267")),
        ("VALIGN", (0,0), (-1,-1), "TOP"), ("GRID", (0,0), (-1,-1), .3, colors.HexColor("#C9D8E1")),
        ("LEFTPADDING", (0,0), (-1,-1), 6), ("RIGHTPADDING", (0,0), (-1,-1), 6),
        ("TOPPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ]))
    story += [table, Spacer(1, 6)]
    story += [p("A large one-time backfill is a cursor-driven workflow, not a single long process: enumerators checkpoint source pages, each URL is placed on a durable queue, and workers write terminal outcomes. Failed tasks use a dead-letter queue with reason and retry schedule. Capacity changes (workers, queue partitions, and database IOPS) increase throughput without code changes.", body)]
    story += [p("2. Record quality and entity resolution", h),
              p("Every schema includes source name, original URL, collection timestamp, and a schema version. Startup/product imports reject missing or malformed URLs. Research paper records originate from arXiv; GitHub star counts are retrieved only from the GitHub API and timestamped on collection. The resolver first applies a conservative normalization (case, punctuation, corporate suffixes), then thresholded fuzzy matching against seed canonicals. Low-confidence matches remain unresolved and are logged rather than silently merged.", body)]
    story += [p("Operational invariant: preserve raw snapshot, extracted field evidence, resolver version, and source URL so any record can be audited or reprocessed.", bullet,)]
    story.append(PageBreak())

    story += [p("Reliability and Freshness Controls", title), p("Failure-tolerant extraction at high concurrency", subtitle)]
    story += [p("3. Exact handling of 413 and 429", h)]
    rows = [
        [p("Condition", small), p("Worker behavior", small), p("Safety property", small)],
        [p("413 Payload Too Large", small), p("Never submit whole raw pages. First retain the raw snapshot, extract readable article text, then chunk on paragraph/sentence boundaries under a provider-specific character/token budget. Retry only the smaller chunk.", small), p("Dense content is retained while request size is bounded; chunk identifiers retain parent URL and offsets.", small)],
        [p("429 Rate Limited", small), p("Honor Retry-After when supplied; otherwise exponential backoff with jitter. Reduce the affected provider/source concurrency and proceed with the next configured LLM provider when appropriate.", small), p("Avoids synchronized retry storms and protects independent sources from one provider outage.", small)],
        [p("Timeout / 5xx", small), p("Bounded retries with jitter; after exhaustion persist a retryable failure to the queue/DLQ.", small), p("No task disappears and no request loops indefinitely.", small)],
    ]
    table = Table(rows, colWidths=[1.25*inch, 3.65*inch, 1.65*inch], repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#E6F3F6")),("GRID",(0,0),(-1,-1),.3,colors.HexColor("#C9D8E1")),("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),6),("RIGHTPADDING",(0,0),(-1,-1),6),("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)]))
    story += [table, Spacer(1, 7)]
    story += [p("LLM chain", h), p("The production order is Gemini Flash, Groq-hosted Llama, then DeepSeek, subject to configured credentials and policy. Providers expose a common extract interface. Prompt contracts require JSON and explicitly forbid unsupported inference. Validate JSON against the target schema, retain per-field source snippets, and reject records without provenance. Deterministic parsers handle dates and common metadata before any LLM call to reduce cost and hallucination risk.", body)]
    story += [p("4. Freshness and distributed deduplication", h),
              p("For news and jobs, the worker normalizes RSS/Atom timestamps and page metadata to UTC. A record is accepted only if published in the last 24 hours (with a small future-skew tolerance). Relative labels such as “2 hours ago” are evaluated against collection time. When no trustworthy date exists, do not claim freshness: store the URL as pending and use a source-specific change detector (first-seen time, feed position, content hash, and next-run confirmation) for review.", body),
              p("A globally unique ledger keyed by SHA-256(normalized URL) prevents multiple nodes from accepting the same URL. A second key, URL + content hash + parser/schema version, controls reprocessing when pages change. In Postgres, `INSERT ... ON CONFLICT DO NOTHING` claims a URL atomically; event rows record fetch, parse, quality-gate, and export outcomes. This provides exactly-once acceptance even though fetching remains at-least-once.", body)]
    story += [p("5. Monitoring", h), p("Emit structured logs with run ID, source, URL hash, status, retry count, latency, freshness decision, and resolver confidence. Alert on queue lag, 429/403 spikes, stale feeds, parser errors, LLM fallback frequency, and abnormal source volume. Dashboards separate availability from verified data quality.", body)]
    story.append(PageBreak())

    story += [p("Storage, Compliance, and Delivery", title), p("Graph-ready data without sacrificing raw evidence", subtitle)]
    story += [p("6. Storage strategy", h)]
    rows = [
        [p("Data", small), p("System", small), p("Reason", small)],
        [p("Raw responses", small), p("S3/GCS-compatible object storage", small), p("Low-cost immutable source snapshots; retention and replay.", small)],
        [p("Canonical records + ledger", small), p("Postgres", small), p("ACID URL claims, relational provenance, JSONB evolving schemas, straightforward bulk upserts.", small)],
        [p("Relationships", small), p("Neo4j or Postgres/Apache AGE derived graph", small), p("Maps startup-founder-product-paper-job relationships and supports graph traversal.", small)],
        [p("Semantic retrieval", small), p("pgvector initially; dedicated vector service if scale warrants", small), p("Keeps embeddings near metadata; migrate only when latency/volume requires it.", small)],
        [p("Analytics", small), p("Parquet in a lakehouse + warehouse", small), p("Cheap historical scans and reproducible model features.", small)],
    ]
    table = Table(rows, colWidths=[1.55*inch, 2.55*inch, 2.45*inch], repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#E6F3F6")),("GRID",(0,0),(-1,-1),.3,colors.HexColor("#C9D8E1")),("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),6),("RIGHTPADDING",(0,0),(-1,-1),6),("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)]))
    story += [table, Spacer(1, 7)]
    story += [p("7. Anti-bot and JavaScript-rendered sources", h), p("The appropriate strategy is compliance-first, not CAPTCHA bypass. Prefer licensed data, documented APIs, RSS feeds, partner exports, or explicit written permission. For a permitted JavaScript-rendered source, run Playwright asynchronously with a persistent, rate-limited browser context, render only pages discovered from allowed indexes, and cache snapshots. Observe robots.txt, terms, source-specific request budgets, and a kill switch. For Cloudflare/DataDome blocks, stop automated requests, record the block signal, and escalate to an official API, commercial data agreement, or manual authorization workflow. The pipeline must never attempt to defeat CAPTCHAs or access controls.", body)]
    story += [p("8. Deployment and acceptance", h), p("Deploy containers as scheduled discovery jobs plus queue consumers. Secrets live in a managed vault; source credentials and LLM keys never enter logs or exports. CI runs unit tests, schema fixtures, date-parsing regressions, and mocked 413/429 retries. A staging run validates row-level provenance before production promotion. The export service writes six tabs/files: Startups, Products, Research Papers, Jobs, News, and Entity Mapping Log.", body)]
    story += [p("Acceptance checklist", h)]
    for text in ["1,000 distinct source-backed startups and products supplied by approved directory/API imports.", "1,000 arXiv/Papers with Code research papers, with GitHub URL/star values only when a source association is verified.", "All exported jobs/news pass the 24-hour UTC gate; undated items are excluded or marked pending.", "Every exported entity maps to its original source URL; resolver decisions and operational failures are auditable."]:
        story.append(p("• " + text, bullet))
    story += [Spacer(1, 8), p("Implementation companion: `README.md` and `src/intel_pipeline/`", small)]
    doc.build(story, onFirstPage=footer, onLaterPages=footer)


if __name__ == "__main__":
    main()
