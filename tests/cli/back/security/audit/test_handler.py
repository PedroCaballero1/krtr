"""Tests `krtr back security audit sync-auth-events`: it reports the run, or fails clearly."""

import pytest
from typer.testing import CliRunner

from krtr.back.security.audit.artifacts import AuthEventSyncResult
from krtr.cli.back.security.audit import handler
from krtr.cli.main import app

runner = CliRunner()
COMMAND = ["back", "security", "audit", "sync-auth-events"]


def fail_without_audit_url() -> AuthEventSyncResult:
    """Stands in for the sync when KRTR_AUDIT_DB_URL is missing."""
    raise ValueError("Missing required environment variable: KRTR_AUDIT_DB_URL")


def test_sync_reports_how_many_events_were_new(monkeypatch: pytest.MonkeyPatch) -> None:
    """The output tells events already copied apart from new ones."""
    result = AuthEventSyncResult(since=None, read=3, inserted=2)
    monkeypatch.setattr(handler, "sync_auth_events_from_environment", lambda: result)

    outcome = runner.invoke(app, COMMAND)

    assert outcome.exit_code == 0, outcome.output
    assert "Keycloak events: 3 read, 2 new" in outcome.output


def test_sync_fails_with_exit_1_naming_the_missing_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A configuration error exits with 1 and says what is missing."""
    monkeypatch.setattr(handler, "sync_auth_events_from_environment", fail_without_audit_url)

    outcome = runner.invoke(app, COMMAND)

    assert outcome.exit_code == 1
    assert "KRTR_AUDIT_DB_URL" in outcome.output
