"""Tests for the environment doctor: every check reports its own result."""

import sys
from typing import Any

import pytest

from krtr.compute.modal import doctor
from krtr.compute.modal.config import DoctorCheckName, ModalConfig
from krtr.compute.modal.doctor import run_doctor
from tests.compute.modal.fakes import FakeSecretSdk, install_fake_secret_sdk


class ConnectableNeonClient:
    """Stands in for NeonClient, opening a connection that always succeeds."""

    def close(self) -> None:
        """Pretends to close the connection."""


def _failing_neon_client() -> Any:
    """Stands in for NeonClient when the connection string is missing."""
    raise ValueError("Missing required environment variable: NEON_DB_HOST")


@pytest.fixture
def sdk(monkeypatch: pytest.MonkeyPatch) -> FakeSecretSdk:
    """A working fake Modal SDK, with a Neon client that connects."""
    monkeypatch.setattr(doctor, "NeonClient", ConnectableNeonClient)
    return install_fake_secret_sdk(monkeypatch)


def _by_name(report: Any) -> dict[DoctorCheckName, Any]:
    """Indexes a report's checks by name."""
    return {check.name: check for check in report.checks}


def test_a_healthy_environment_passes_every_check(sdk: FakeSecretSdk) -> None:
    """With Neon reachable, credentials accepted and the secret present, all is well."""
    report = run_doctor(ModalConfig())

    assert report.passed
    assert [check.name for check in report.checks] == [
        DoctorCheckName.NEON_CONNECTION,
        DoctorCheckName.MODAL_CREDENTIALS,
        DoctorCheckName.MODAL_SECRET,
    ]


def test_the_secret_is_looked_up_by_its_configured_name_with_the_required_keys(
    sdk: FakeSecretSdk,
) -> None:
    """The check must fail when the secret lacks the variable tasks need, not just exist."""
    run_doctor(ModalConfig(secret_name="custom-secret"))

    assert sdk.looked_up == [("custom-secret", ["NEON_DB_HOST"])]


def test_a_neon_failure_is_reported_without_hiding_the_modal_checks(
    monkeypatch: pytest.MonkeyPatch, sdk: FakeSecretSdk
) -> None:
    """Neon and Modal are independent routes: one failing must not stop the other's report."""
    monkeypatch.setattr(doctor, "NeonClient", _failing_neon_client)

    checks = _by_name(run_doctor(ModalConfig()))

    assert not checks[DoctorCheckName.NEON_CONNECTION].passed
    assert "NEON_DB_HOST" in checks[DoctorCheckName.NEON_CONNECTION].detail
    assert checks[DoctorCheckName.MODAL_CREDENTIALS].passed
    assert checks[DoctorCheckName.MODAL_SECRET].passed


def test_bad_credentials_fail_and_the_secret_is_reported_as_not_checked(
    sdk: FakeSecretSdk,
) -> None:
    """Without working credentials the secret cannot be looked up, and the report must say so."""
    sdk.list_error = RuntimeError("Token missing or invalid")

    checks = _by_name(run_doctor(ModalConfig()))

    assert not checks[DoctorCheckName.MODAL_CREDENTIALS].passed
    assert "invalid" in checks[DoctorCheckName.MODAL_CREDENTIALS].detail
    assert not checks[DoctorCheckName.MODAL_SECRET].passed
    assert "Not checked" in checks[DoctorCheckName.MODAL_SECRET].detail
    assert sdk.looked_up == []


def test_a_missing_secret_fails_and_says_how_to_create_it(sdk: FakeSecretSdk) -> None:
    """The fix for a missing secret is one command, and the report must name it."""
    sdk.hydrate_error = LookupError("Secret 'krtr-neon' not found")

    check = _by_name(run_doctor(ModalConfig()))[DoctorCheckName.MODAL_SECRET]

    assert not check.passed
    assert "not found" in check.detail
    assert "krtr compute modal secrets sync" in check.detail


def test_a_missing_modal_sdk_is_reported_with_the_install_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Users of the local route do not have Modal; the report must say how to get it."""
    monkeypatch.setattr(doctor, "NeonClient", ConnectableNeonClient)
    monkeypatch.setitem(sys.modules, "modal", None)

    checks = _by_name(run_doctor(ModalConfig()))

    assert checks[DoctorCheckName.NEON_CONNECTION].passed
    assert "uv sync --extra modal" in checks[DoctorCheckName.MODAL_CREDENTIALS].detail
    assert not run_doctor(ModalConfig()).passed
