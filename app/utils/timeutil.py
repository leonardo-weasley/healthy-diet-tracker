import re
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from ..runtime import settings

from .errors import InvalidRequest


def _tz():
    return ZoneInfo(settings()['APP_TIMEZONE'])


def _datetime(value):
    if value is None:
        return datetime.now(_tz())
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00')) if isinstance(value, str) else value
        if not isinstance(parsed, datetime):
            raise ValueError()
        return parsed.replace(tzinfo=_tz()) if parsed.tzinfo is None else parsed
    except (TypeError, ValueError, OverflowError):
        raise InvalidRequest('Invalid ISO 8601 datetime.') from None


def to_utc_iso(value):
    return _datetime(value).astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def to_local_iso(value):
    return _datetime(value).astimezone(_tz()).isoformat(timespec='seconds')


def local_date_of(value):
    return _datetime(value).astimezone(_tz()).date().isoformat()


def today_local():
    return local_date_of(None)


def validate_date(value):
    try:
        if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            raise ValueError()
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise InvalidRequest('Date must be a valid YYYY-MM-DD value.') from None
