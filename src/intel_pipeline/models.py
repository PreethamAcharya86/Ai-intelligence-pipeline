from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(slots=True)
class Source:
    name: str
    url: str


@dataclass(slots=True)
class Startup:
    source: Source
    entity_name: str
    description: str
    employee_count: int | None = None
    schema_version: str = "1.0"
    record_type: Literal["STARTUP"] = "STARTUP"
    collected_at: str = field(default_factory=utc_now)

    def row(self) -> dict[str, Any]:
        return {"schemaVersion": self.schema_version, "recordType": self.record_type,
                "source.name": self.source.name, "source.url": self.source.url,
                "content.entityName": self.entity_name, "content.description": self.description,
                "content.data.employeeCount": self.employee_count, "collectedAt": self.collected_at}


@dataclass(slots=True)
class Product:
    source: Source
    startup_name: str
    product_name: str
    pricing_model: Literal["FREE", "FREEMIUM", "PAID", "ENTERPRISE", "UNKNOWN"] = "UNKNOWN"
    schema_version: str = "1.0"
    record_type: Literal["PRODUCT"] = "PRODUCT"
    collected_at: str = field(default_factory=utc_now)

    def row(self) -> dict[str, Any]:
        return {"schemaVersion": self.schema_version, "recordType": self.record_type,
                "source.name": self.source.name, "source.url": self.source.url,
                "content.startupName": self.startup_name, "content.productName": self.product_name,
                "content.pricingModel": self.pricing_model, "collectedAt": self.collected_at}


@dataclass(slots=True)
class ResearchPaper:
    source: Source
    title: str
    authors: list[str]
    paper_url: str
    published_date: str
    github_url: str | None = None
    github_stars: int | None = None
    schema_version: str = "1.0"
    record_type: Literal["RESEARCH_PAPER"] = "RESEARCH_PAPER"
    collected_at: str = field(default_factory=utc_now)

    def row(self) -> dict[str, Any]:
        return {"schemaVersion": self.schema_version, "recordType": self.record_type,
                "source.name": self.source.name, "source.url": self.source.url,
                "content.title": self.title, "content.authors": "; ".join(self.authors),
                "content.paper_url": self.paper_url, "content.github_url": self.github_url,
                "content.github_stars": self.github_stars, "content.published_date": self.published_date,
                "collectedAt": self.collected_at}


@dataclass(slots=True)
class Signal:
    kind: Literal["NEWS", "JOB"]
    source: Source
    title: str
    url: str
    published_at: str
    full_text: str
    company: str | None = None
    is_remote: bool | None = None
    role_family: str | None = None
    freshness_basis: str = "explicit_timestamp"
    schema_version: str = "1.0"
    collected_at: str = field(default_factory=utc_now)

    def row(self) -> dict[str, Any]:
        base = {"schemaVersion": self.schema_version, "recordType": self.kind,
                "source.name": self.source.name, "source.url": self.source.url,
                "content.title": self.title, "content.url": self.url,
                "content.date": self.published_at, "content.fullText": self.full_text,
                "content.freshnessBasis": self.freshness_basis, "collectedAt": self.collected_at}
        if self.kind == "JOB":
            base.update({"content.company": self.company, "content.is_remote": self.is_remote,
                         "content.role_family": self.role_family})
        return base


def record_to_dict(record: Any) -> dict[str, Any]:
    return asdict(record)
