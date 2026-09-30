"""Tests record_http_request: it fires an http_request event, in the background."""

import os
from typing import Any

from fastapi.testclient import TestClient

from krtr.back.security.audit.event_names import EventName
from krtr.back.security.audit.recorder import EventRecorder
from krtr.back.security.crypto.cipher import AesGcmCipher
from krtr.back.web.app import create_app
from krtr.back.web.config import WebConfig


class RecordingClient:
    """Stands in for NeonClient, capturing execute_params calls instead of writing."""

    def __init__(self) -> None:
        """Starts with no recorded calls."""
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def execute_params(self, statement: str, params: dict[str, Any] | None = None) -> None:
        """Records the statement and params instead of touching a database."""
        self.calls.append((statement, params or {}))


def test_a_request_schedules_an_http_request_event() -> None:
    """Verifies the background task records exactly one http_request event."""
    client = RecordingClient()
    recorder = EventRecorder(client=client, cipher=AesGcmCipher(os.urandom(32)))
    app = create_app(WebConfig(), event_recorder=recorder)
    test_client = TestClient(app)

    response = test_client.get("/healthz")

    assert response.status_code == 200
    assert len(client.calls) == 1
    _, params = client.calls[0]
    assert params["event_name"] == EventName.HTTP_REQUEST.value


def test_no_event_is_recorded_when_no_recorder_is_configured() -> None:
    """A missing recorder must degrade gracefully (no crash), not queue anything."""
    app = create_app(WebConfig())  # No event_recorder given.
    test_client = TestClient(app)

    response = test_client.get("/healthz")

    assert response.status_code == 200
    assert app.state.event_recorder is None
