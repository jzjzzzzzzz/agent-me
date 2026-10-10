"""UTC validity and episode identity; observation time is not event time."""

from datetime import UTC, datetime


def utc(value):
    if value is None:
        return None
    date = datetime.fromisoformat(value) if isinstance(value, str) else value
    if not isinstance(date, datetime) or date.tzinfo is None or date.utcoffset() is None:
        raise ValueError("Time must be a timezone-aware datetime")
    return date.astimezone(UTC)


def iso(value):
    date = utc(value)
    return date.isoformat() if date is not None else None


def active_at(item, at):
    start, end, occurrence = (
        utc(item.get(field)) for field in ("valid_from", "valid_until", "occurred_at")
    )
    return (
        (start is None or start <= at)
        and (end is None or at < end)
        and (occurrence is None or occurrence <= at)
    )


def overlaps(left, right):
    if left["kind"] in {"event", "decision"}:
        a, b = utc(left.get("occurred_at")), utc(right.get("occurred_at"))
        if a is not None and b is not None and a != b:
            return False
    start = max(
        utc(left.get("valid_from")) or datetime.min.replace(tzinfo=UTC),
        utc(right.get("valid_from")) or datetime.min.replace(tzinfo=UTC),
    )
    end = min(
        utc(left.get("valid_until")) or datetime.max.replace(tzinfo=UTC),
        utc(right.get("valid_until")) or datetime.max.replace(tzinfo=UTC),
    )
    return start < end
