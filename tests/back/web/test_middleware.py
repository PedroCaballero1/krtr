"""Tests krtr-web's request middleware: the request_id and the body size limit."""

from fastapi.testclient import TestClient

from krtr.back.web.app import create_app
from krtr.back.web.config import WebConfig
from krtr.back.web.middleware import MAX_REQUEST_BYTES


def client() -> TestClient:
    """Builds the app with no collaborators; the size limit applies before any route."""
    return TestClient(create_app(WebConfig()), base_url="https://testserver")


def test_an_oversized_body_is_refused_before_any_route_reads_it() -> None:
    """Without a session, a huge upload must still be refused, not spooled to disk."""
    response = client().post(
        "/api/chat/voice",
        content=b"x" * (MAX_REQUEST_BYTES + 1),
        headers={"content-type": "multipart/form-data; boundary=x"},
    )

    assert response.status_code == 413
    assert response.json()["error"] == "request_too_large"


def test_a_malformed_content_length_is_refused() -> None:
    """A Content-Length that is not a number cannot be trusted to bound the body."""
    response = client().post("/api/events", headers={"content-length": "abc"}, content=b"")

    assert response.status_code == 413


def test_a_body_within_the_limit_reaches_the_route() -> None:
    """The limit leaves room for a 2 MB voice note and its multipart framing."""
    response = client().post("/api/events", content=b"x" * 1000)

    assert response.status_code != 413
