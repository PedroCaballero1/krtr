"""Tests create_app() (health, docs, SPA fallback) and create_served_app() (event recording)."""

import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from krtr.back.security.audit import recorder as recorder_module
from krtr.back.security.audit.event_names import EventName
from krtr.back.security.audit.recorder import EventRecorder
from krtr.back.security.crypto.config import CryptoEnvironmentVariable
from krtr.back.web import app as app_module
from krtr.back.web.app import create_app
from krtr.back.web.config import WebConfig, WebEnvironment, WebEnvironmentVariable
from tests.back.security.audit.fakes import InMemoryRecorder, refuse_to_open_neon


@pytest.fixture
def served_environment(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Isolates create_served_app from the developer's .env, the events key and Neon."""
    monkeypatch.setattr(app_module, "load_dotenv", lambda: None)
    monkeypatch.setattr(recorder_module, "NeonClient", refuse_to_open_neon)
    monkeypatch.delenv(CryptoEnvironmentVariable.EVENTS_KEY, raising=False)
    return monkeypatch


def test_healthz_reports_ok() -> None:
    """Verifies GET /healthz returns 200 with the expected body."""
    client = TestClient(create_app(WebConfig()))

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_docs_are_disabled_in_production() -> None:
    """Verifies /docs, /redoc and /openapi.json all 404 under the production config."""
    client = TestClient(create_app(WebConfig(environment=WebEnvironment.PRODUCTION)))

    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_docs_are_enabled_in_development() -> None:
    """Verifies /docs and /openapi.json are served under the development config."""
    client = TestClient(create_app(WebConfig(environment=WebEnvironment.DEVELOPMENT)))

    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_spa_fallback_404s_when_the_frontend_is_not_built(tmp_path: Path) -> None:
    """A dist directory with no index.html (frontend not built yet) must 404, not crash."""
    client = TestClient(create_app(WebConfig(frontend_dist_dir=tmp_path / "does-not-exist")))

    response = client.get("/app")

    assert response.status_code == 404


def test_spa_fallback_serves_index_html_for_app_routes(tmp_path: Path) -> None:
    """Any route the SPA owns (/, /app, /app/support) must resolve to index.html."""
    (tmp_path / "index.html").write_text("<html>krtr</html>")
    client = TestClient(create_app(WebConfig(frontend_dist_dir=tmp_path)))

    for path in ("/", "/app", "/app/support"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert response.text == "<html>krtr</html>"


def test_spa_fallback_does_not_swallow_reserved_prefixes(tmp_path: Path) -> None:
    """A future /api/* or /auth/* route must 404 through the fallback, not serve HTML."""
    (tmp_path / "index.html").write_text("<html>krtr</html>")
    client = TestClient(create_app(WebConfig(frontend_dist_dir=tmp_path)))

    assert client.get("/api/whatever").status_code == 404
    assert client.get("/auth/whatever").status_code == 404


def test_frontend_assets_are_served_when_built(tmp_path: Path) -> None:
    """A file under dist/assets/ must be served at /assets/... once mounted."""
    (tmp_path / "index.html").write_text("<html>krtr</html>")
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (assets_dir / "app.js").write_text("console.log('krtr')")
    client = TestClient(create_app(WebConfig(frontend_dist_dir=tmp_path)))

    response = client.get("/assets/app.js")

    assert response.status_code == 200
    assert response.text == "console.log('krtr')"


def test_response_carries_a_request_id_header() -> None:
    """Every response must carry the X-Request-Id header for traceability (§3.4)."""
    client = TestClient(create_app(WebConfig()))

    response = client.get("/healthz")

    assert response.headers.get("X-Request-Id")


def test_served_app_records_every_request_in_production(
    served_environment: pytest.MonkeyPatch,
) -> None:
    """In production, the served app must record an http_request for each request (G21)."""
    recorder = InMemoryRecorder()
    served_environment.setenv(WebEnvironmentVariable.ENVIRONMENT, WebEnvironment.PRODUCTION)
    served_environment.setattr(EventRecorder, "from_environment", lambda: recorder)

    TestClient(app_module.create_served_app()).get("/healthz")

    assert [event_name for event_name, _ in recorder.events] == [EventName.HTTP_REQUEST]


def test_served_app_refuses_to_start_in_production_without_the_events_key(
    served_environment: pytest.MonkeyPatch,
) -> None:
    """Production must fail fast, naming the missing variable, instead of dropping events."""
    served_environment.setenv(WebEnvironmentVariable.ENVIRONMENT, WebEnvironment.PRODUCTION)

    with pytest.raises(ValueError, match=CryptoEnvironmentVariable.EVENTS_KEY.value):
        app_module.create_served_app()


def test_served_app_runs_without_recording_in_development(
    served_environment: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Development may run without Neon or a key: recording is off and a warning says why."""
    served_environment.setenv(WebEnvironmentVariable.ENVIRONMENT, WebEnvironment.DEVELOPMENT)

    with caplog.at_level(logging.WARNING, logger=app_module.__name__):
        served_app = app_module.create_served_app()

    assert served_app.state.event_recorder is None
    assert CryptoEnvironmentVariable.EVENTS_KEY.value in caplog.text
    assert TestClient(served_app).get("/healthz").status_code == 200
