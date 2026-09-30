"""Tests WebConfig's environment loading and its docs_enabled gate."""

from pathlib import Path

import pytest

from krtr.back.web.config import WebConfig, WebEnvironment, WebEnvironmentVariable


def test_default_config_is_production_with_docs_disabled() -> None:
    """A config built with no overrides must fail closed: no docs in prod."""
    config = WebConfig()

    assert config.environment is WebEnvironment.PRODUCTION
    assert config.docs_enabled is False


def test_development_environment_enables_docs() -> None:
    """Explicitly choosing development must be the only way to expose docs."""
    config = WebConfig(environment=WebEnvironment.DEVELOPMENT)

    assert config.docs_enabled is True


def test_from_environment_reads_environment_and_dist_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies both env vars are read and override the defaults."""
    monkeypatch.setenv(WebEnvironmentVariable.ENVIRONMENT, "development")
    monkeypatch.setenv(WebEnvironmentVariable.FRONTEND_DIST_DIR, "/tmp/dist")

    config = WebConfig.from_environment()

    assert config.environment is WebEnvironment.DEVELOPMENT
    assert config.frontend_dist_dir == Path("/tmp/dist")


def test_from_environment_defaults_to_production_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifies a missing environment variable falls back to production, not development."""
    monkeypatch.delenv(WebEnvironmentVariable.ENVIRONMENT, raising=False)

    config = WebConfig.from_environment()

    assert config.environment is WebEnvironment.PRODUCTION
