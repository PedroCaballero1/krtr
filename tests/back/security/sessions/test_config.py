"""Tests SessionConfig: its defaults are G15's limits."""

from datetime import timedelta

from krtr.back.security.sessions.config import SESSION_COOKIE_NAME, SessionConfig


def test_defaults_are_the_g15_limits() -> None:
    """5 minutes idle, 30 at most, and a refresh with a minute to spare."""
    config = SessionConfig()

    assert config.idle_timeout == timedelta(minutes=5)
    assert config.absolute_timeout == timedelta(minutes=30)
    assert config.token_refresh_margin == timedelta(seconds=60)


def test_the_cookie_name_has_the_host_prefix() -> None:
    """`__Host-` stops other *.modal.run apps from setting or shadowing the session cookie (D22)."""
    assert SESSION_COOKIE_NAME.startswith("__Host-")
