"""Tests for copying the allowed environment variables into the Modal secret."""

import logging

import pytest

from krtr.compute.modal import secrets
from krtr.compute.modal.secrets import push_secret, read_forwarded_variables, sync_secret
from tests.compute.modal.fakes import install_fake_secret_sdk

CONNECTION_STRING = "postgresql://user:hunter2@host/db?sslmode=require"


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stops the tests reading the developer's real `.env` or inheriting its variables."""
    monkeypatch.setattr(secrets, "load_dotenv", lambda: None)
    monkeypatch.delenv("NEON_DB_HOST", raising=False)


def test_only_the_allowed_variables_are_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """Other credentials in the environment must never be forwarded to Modal."""
    monkeypatch.setenv("NEON_DB_HOST", CONNECTION_STRING)
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "aws-secret")
    monkeypatch.setenv("MODAL_TOKEN_SECRET", "modal-secret")

    assert read_forwarded_variables() == {"NEON_DB_HOST": CONNECTION_STRING}


@pytest.mark.parametrize("value", [None, ""])
def test_a_missing_or_empty_variable_is_reported_by_name(
    monkeypatch: pytest.MonkeyPatch, value: str | None
) -> None:
    """Syncing an empty connection string would break every remote run later."""
    if value is not None:
        monkeypatch.setenv("NEON_DB_HOST", value)

    with pytest.raises(ValueError, match="NEON_DB_HOST"):
        read_forwarded_variables()


def test_push_overwrites_the_values_of_an_existing_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A rotated password must reach Modal: `create(allow_existing=True)` alone keeps old values."""
    sdk = install_fake_secret_sdk(monkeypatch)

    push_secret("krtr-neon", {"NEON_DB_HOST": CONNECTION_STRING})

    assert sdk.created == [("krtr-neon", {"NEON_DB_HOST": CONNECTION_STRING}, True)]
    assert sdk.events == ["create", "hydrate", "update"]
    assert sdk.updated_values == {"NEON_DB_HOST": CONNECTION_STRING}
    assert sdk.looked_up == [("krtr-neon", [])]


def test_sync_stores_the_variables_and_returns_their_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sync must read the environment and push exactly the allowed variables."""
    sdk = install_fake_secret_sdk(monkeypatch)
    monkeypatch.setenv("NEON_DB_HOST", CONNECTION_STRING)

    names = sync_secret("krtr-neon")

    assert names == ["NEON_DB_HOST"]
    assert sdk.updated_values == {"NEON_DB_HOST": CONNECTION_STRING}


def test_sync_never_logs_a_secrets_value(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Logs are shared and kept; the password inside the connection string must not be in them."""
    install_fake_secret_sdk(monkeypatch)
    monkeypatch.setenv("NEON_DB_HOST", CONNECTION_STRING)

    with caplog.at_level(logging.DEBUG):
        sync_secret("krtr-neon")

    assert "NEON_DB_HOST" in caplog.text
    assert "hunter2" not in caplog.text


def test_sync_fails_before_contacting_modal_when_a_variable_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nothing must be created on Modal if the environment is incomplete."""
    sdk = install_fake_secret_sdk(monkeypatch)

    with pytest.raises(ValueError, match="NEON_DB_HOST"):
        sync_secret("krtr-neon")

    assert sdk.events == []
