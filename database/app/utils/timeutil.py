"""Timezone helpers.

``meal_datetime_utc`` is stored as a UTC ISO-8601 string ending in ``Z``;
API responses expose it in the configured local timezone.  Member 1 owns the
final implementation (``app/utils/timeutil.py``); this version implements the
same two functions the database layer needs.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from flask import current_app, has_app_context

DEFAULT_TIMEZONE = "Asia/Shanghai"


def timezone_name(name: str | None = None) -> str:
    if name:
        return name
    if has_app_context():
        return current_app.config.get("APP_TIMEZONE", DEFAULT_TIMEZONE)
    return DEFAULT_TIMEZONE


def _zone(name: str | None = None) -> timezone | ZoneInfo:
    try:
        return ZoneInfo(timezone_name(name))
    except Exception:
        # ``tzdata`` may be missing on a bare Windows install.  China has no
        # DST, so a fixed +08:00 is a correct fallback for the default zone.
        if timezone_name(name) == DEFAULT_TIMEZONE:
            return timezone(timedelta(hours=8))
        return timezone.utc


def parse_utc(value: str) -> datetime:
    """Parse an ISO-8601 string; a missing offset means UTC."""
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def to_local_iso(utc_iso: str | None, tz: str | None = None) -> str | None:
    if not utc_iso:
        return None
    return parse_utc(utc_iso).astimezone(_zone(tz)).isoformat(timespec="seconds")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")


def local_now(tz: str | None = None) -> datetime:
    return utc_now().astimezone(_zone(tz))


def local_today(tz: str | None = None) -> str:
    return local_now(tz).date().isoformat()


def to_local_datetime(utc_iso: str | None, tz: str | None = None) -> datetime | None:
    if not utc_iso:
        return None
    return parse_utc(utc_iso).astimezone(_zone(tz))
