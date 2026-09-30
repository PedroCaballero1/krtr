"""Tests HeadersConfig's environment loading and default."""

import pytest

from krtr.back.security.headers.config import (
    DEFAULT_AUTH_ORIGIN,
    HeadersConfig,
    HeadersEnvironmentVariable,
)


def test_default_auth_origin_is_local_keycloak() -> None:
    """A config built with no overrides must point at the local dev Keycloak."""
    config = HeadersConfig()

    assert config.auth_origin == DEFAULT_AUTH_ORIGIN


def test_from_environment_reads_the_auth_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies KRTR_AUTH_ORIGIN overrides the default."""
    monkeypatch.setenv(HeadersEnvironmentVariable.AUTH_ORIGIN, "https://auth.example.com")

    config = HeadersConfig.from_environment()

    assert config.auth_origin == "https://auth.example.com"
