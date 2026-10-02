"""Defines the clock the security verticals read the current time from.

Exists so time-dependent rules (the login cookie's 10 minutes, the 5-minute idle and 30-minute
absolute sessions of G15, token refresh) take the clock as a dependency: production uses the
real UTC time and tests pass a fake one they can move forward. Consumed by
`krtr/back/security/oidc/` and `krtr/back/security/sessions/`.
"""

from collections.abc import Callable
from datetime import UTC, datetime

Clock = Callable[[], datetime]


def utc_now() -> datetime:
    """Returns the current time, timezone-aware in UTC.

    Exists as the default `Clock`, so every caller gets aware UTC datetimes, which compare
    correctly with the `TIMESTAMPTZ` columns of `app_sessions`.

    Args:
        None.

    Returns:
        datetime: the current time in UTC.
    """
    return datetime.now(UTC)
