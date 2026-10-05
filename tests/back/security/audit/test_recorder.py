"""Tests EventRecorder: the DB write is encrypted, opaque, and reversible."""

import base64
import json
import os
from typing import Any
from uuid import UUID

import pytest

from krtr.back.security.audit import recorder as recorder_module
from krtr.back.security.audit.event_names import EventName
from krtr.back.security.audit.recorder import EventRecorder
from krtr.back.security.crypto.cipher import AesGcmCipher
from krtr.back.security.crypto.config import CryptoEnvironmentVariable
from tests.back.security.audit.fakes import refuse_to_open_neon

KEY = os.urandom(32)


class RecordingClient:
    """Stands in for NeonClient, capturing execute_params calls instead of writing."""

    def __init__(self) -> None:
        """Starts with no recorded calls."""
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def execute_params(self, statement: str, params: dict[str, Any] | None = None) -> None:
        """Records the statement and params instead of touching a database."""
        self.calls.append((statement, params or {}))


def make_recorder() -> tuple[EventRecorder, RecordingClient]:
    """Builds an EventRecorder backed by a RecordingClient and a real cipher."""
    client = RecordingClient()
    recorder = EventRecorder(client=client, cipher=AesGcmCipher(KEY))
    return recorder, client


def test_record_event_writes_one_row_with_a_valid_uuid_and_event_name() -> None:
    """Verifies the row's id is a real UUID and event_name matches the enum value."""
    recorder, client = make_recorder()

    recorder.record_event(EventName.PAGE_VIEW, {"path": "/app"})

    assert len(client.calls) == 1
    _, params = client.calls[0]
    assert UUID(params["id"])  # Raises ValueError if not a valid UUID.
    assert params["event_name"] == "page_view"


def test_stored_properties_are_not_readable_json() -> None:
    """The core requirement of §3.5: properties must not be plaintext JSON in the row."""
    recorder, client = make_recorder()
    properties = {"customer_id": "12345", "incident_id": "abc-999"}

    recorder.record_event(EventName.CASE_RESUME_SUCCEEDED, properties)

    _, params = client.calls[0]
    stored_bytes = params["properties"]
    assert isinstance(stored_bytes, bytes)
    assert b"customer_id" not in stored_bytes
    assert b"12345" not in stored_bytes
    with pytest.raises((json.JSONDecodeError, UnicodeDecodeError)):
        json.loads(stored_bytes)


def test_stored_properties_decrypt_back_to_the_original_properties() -> None:
    """Verifies the encryption round trip end to end, through the recorder."""
    recorder, client = make_recorder()
    properties = {"method": "GET", "path": "/healthz", "status": 200}

    recorder.record_event(EventName.HTTP_REQUEST, properties)

    _, params = client.calls[0]
    decrypted = AesGcmCipher(KEY).decrypt(params["properties"])
    assert json.loads(decrypted) == properties


@pytest.mark.parametrize("forbidden_key", ["password", "token", "tokens", "cookie", "Cookie"])
def test_record_event_refuses_properties_with_a_forbidden_key(forbidden_key: str) -> None:
    """Never allow a password/token/cookie into the audit log, even encrypted."""
    recorder, client = make_recorder()

    with pytest.raises(ValueError, match="must never include"):
        recorder.record_event(EventName.AUTH_LOGIN_SUCCEEDED, {forbidden_key: "secret-value"})

    assert client.calls == []


def test_from_environment_encrypts_with_the_events_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """The recorder built from the environment must encrypt with KRTR_EVENTS_KEY."""
    client = RecordingClient()
    monkeypatch.setattr(recorder_module, "NeonClient", lambda: client)
    monkeypatch.setenv(CryptoEnvironmentVariable.EVENTS_KEY, base64.b64encode(KEY).decode())

    EventRecorder.from_environment().record_event(EventName.PAGE_VIEW, {"path": "/app"})

    _, params = client.calls[0]
    assert json.loads(AesGcmCipher(KEY).decrypt(params["properties"])) == {"path": "/app"}


def test_from_environment_rejects_a_missing_key_before_opening_neon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing KRTR_EVENTS_KEY must fail, naming it, without leaving a connection open."""
    monkeypatch.delenv(CryptoEnvironmentVariable.EVENTS_KEY, raising=False)
    monkeypatch.setattr(recorder_module, "NeonClient", refuse_to_open_neon)

    with pytest.raises(ValueError, match=CryptoEnvironmentVariable.EVENTS_KEY.value):
        EventRecorder.from_environment()
