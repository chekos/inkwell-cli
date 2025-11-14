"""Datetime utilities for timezone-aware timestamp handling.

This module provides utilities to ensure consistent timezone-aware datetime
usage throughout the application. Always use timezone-aware datetimes to avoid
comparison errors and DST-related bugs.
"""

from datetime import datetime, timezone


def now_utc() -> datetime:
    """Get current UTC time with timezone info.

    Returns timezone-aware datetime in UTC. Always use this instead of
    datetime.utcnow() or datetime.now() without timezone argument.

    Returns:
        Timezone-aware datetime object in UTC.

    Example:
        >>> from inkwell.utils.datetime import now_utc
        >>> timestamp = now_utc()
        >>> assert timestamp.tzinfo is not None
        >>> assert timestamp.tzinfo == timezone.utc
    """
    return datetime.now(timezone.utc)


def validate_timezone_aware(dt: datetime, name: str = "datetime") -> None:
    """Validate that datetime is timezone-aware.

    Args:
        dt: Datetime object to validate.
        name: Name of the datetime field for error message.

    Raises:
        ValueError: If datetime is naive (no timezone info).

    Example:
        >>> from datetime import datetime, timezone
        >>> from inkwell.utils.datetime import validate_timezone_aware
        >>> aware = datetime.now(timezone.utc)
        >>> validate_timezone_aware(aware)  # OK
        >>> naive = datetime.utcnow()
        >>> validate_timezone_aware(naive)  # Raises ValueError
    """
    if dt.tzinfo is None:
        raise ValueError(
            f"{name} must be timezone-aware. "
            f"Use datetime.now(timezone.utc) or now_utc() "
            f"instead of datetime.utcnow()"
        )


def format_duration(seconds: float) -> str:
    """Format duration in human-readable form.

    Args:
        seconds: Duration in seconds

    Returns:
        Human-readable duration string (e.g., "2h", "45m", "30s")

    Example:
        >>> format_duration(30)
        '30s'
        >>> format_duration(120)
        '2m'
        >>> format_duration(3600)
        '1h'
        >>> format_duration(86400)
        '1d'
    """
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        return f"{int(seconds / 60)}m"
    elif seconds < 86400:
        return f"{int(seconds / 3600)}h"
    else:
        return f"{int(seconds / 86400)}d"
