"""Tests the security verticals' real clock."""

from datetime import UTC, datetime, timedelta

from krtr.back.security.clock import utc_now


def test_utc_now_is_aware_and_in_utc() -> None:
    """Naive datetimes cannot be compared with the TIMESTAMPTZ values read from Neon."""
    now = utc_now()

    assert now.tzinfo is not None and now.utcoffset() == timedelta(0)
    assert abs(now - datetime.now(UTC)) < timedelta(seconds=5)
