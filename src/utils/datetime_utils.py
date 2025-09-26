"""Utility functions for handling timezone-aware datetimes."""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """
    Get the current UTC datetime with timezone awareness.

    Returns:
        Timezone-aware datetime in UTC
    """
    return datetime.now(timezone.utc)


def local_now() -> datetime:
    """
    Get the current local datetime with timezone awareness.

    Returns:
        Timezone-aware datetime in local timezone
    """
    return datetime.now(tz=timezone.utc)


def ensure_timezone_aware(dt: datetime) -> datetime:
    """
    Ensure a datetime is timezone-aware.
    If naive, assumes it's UTC.

    Args:
        dt: Datetime object (naive or aware)

    Returns:
        Timezone-aware datetime
    """
    if dt.tzinfo is None:
        # Assume naive datetime is UTC
        return dt.replace(tzinfo=timezone.utc)
    return dt


def calculate_duration_ms(start: datetime, end: datetime = None) -> int:
    """
    Calculate duration in milliseconds between two datetimes.

    Args:
        start: Start datetime
        end: End datetime (defaults to current UTC time)

    Returns:
        Duration in milliseconds
    """
    if end is None:
        end = utc_now()

    # Ensure both are timezone-aware
    start = ensure_timezone_aware(start)
    end = ensure_timezone_aware(end)

    duration = (end - start).total_seconds() * 1000
    return int(duration)