"""Tests POST /api/events: catalog validation, size limit, and recording."""

import os
from typing import Any

from fastapi.testclient import TestClient

from krtr.back.security.audit.recorder import EventRecorder
from krtr.back.security.crypto.cipher import AesGcmCipher
from krtr.back.security.csrf.config import DEFAULT_PUBLIC_URL, CsrfConfig
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


SAME_ORIGIN = {"Origin": DEFAULT_PUBLIC_URL}  # What the SPA sends when served locally.


def make_client() -> tuple[TestClient, RecordingClient]:
    """Builds a TestClient wired to a recording EventRecorder."""
    client = RecordingClient()
    recorder = EventRecorder(client=client, cipher=AesGcmCipher(os.urandom(32)))
    app = create_app(WebConfig(), event_recorder=recorder, csrf_config=CsrfConfig())
    return TestClient(app, headers=SAME_ORIGIN), client


def test_a_cataloged_event_is_accepted_and_recorded() -> None:
    """Verifies a valid event_name returns 202 and reaches the recorder."""
    test_client, recording_client = make_client()

    response = test_client.post(
        "/api/events", json={"event_name": "page_view", "properties": {"path": "/app"}}
    )

    assert response.status_code == 202
    # One http_request event (from the audit middleware) plus this one.
    event_names = {params["event_name"] for _, params in recording_client.calls}
    assert "page_view" in event_names


def test_an_event_name_outside_the_catalog_is_rejected() -> None:
    """The core requirement of task 4.7: an unknown name must 422, not 202."""
    test_client, _ = make_client()

    response = test_client.post(
        "/api/events", json={"event_name": "not_a_real_event", "properties": {}}
    )

    assert response.status_code == 422


def test_properties_over_4kb_are_rejected() -> None:
    """Verifies the 4 KB serialized-properties limit is enforced."""
    test_client, _ = make_client()
    oversized_properties = {"blob": "x" * 5000}

    response = test_client.post(
        "/api/events", json={"event_name": "page_view", "properties": oversized_properties}
    )

    assert response.status_code == 413


def test_missing_recorder_still_returns_202() -> None:
    """A not-yet-configured recorder must not break the frontend's fire-and-forget call."""
    app = create_app(WebConfig(), csrf_config=CsrfConfig())  # No event_recorder given.
    test_client = TestClient(app, headers=SAME_ORIGIN)

    response = test_client.post("/api/events", json={"event_name": "page_view", "properties": {}})

    assert response.status_code == 202
