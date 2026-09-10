from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from dateutil import parser as date_parser

RELATIVE = re.compile(r"^(?P<count>\d+)\s+(?P<unit>minute|hour|day|week)s?\s+ago$", re.I)


def parse_published(value: str | None, now: datetime | None = None) -> datetime | None:
    """Normalize RSS/HTML timestamps. Relative dates are interpreted in UTC."""
    if not value:
        return None
    now = now or datetime.now(timezone.utc)
    candidate = value.strip()
    matched = RELATIVE.match(candidate)
    if matched:
        count, unit = int(matched["count"]), matched["unit"].lower()
        return now - timedelta(**{f"{unit}s": count})
    try:
        parsed = date_parser.parse(candidate, fuzzy=True)
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def is_fresh(published: datetime | None, hours: int = 24, now: datetime | None = None) -> bool:
    if published is None:
        return False
    now = now or datetime.now(timezone.utc)
    return now - timedelta(hours=hours) <= published <= now + timedelta(minutes=5)


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
