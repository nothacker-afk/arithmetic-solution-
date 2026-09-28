"""Version-safe datetime helpers (Python 3.10 compatible)."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional


def parse_iso(s) -> Optional[datetime]:
    """Parse an ISO-8601 timestamp. Handles trailing Z on all Python versions."""
    if not s:
        return None
    if isinstance(s, datetime):
        return s
    text = str(s).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
