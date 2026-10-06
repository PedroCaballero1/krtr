"""Tests create_app() (health, docs, SPA fallback) and create_served_app() (events and login)."""

import base64
import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from krtr.back.ia.messages import store as message_store_module
from krtr.back.security.audit import recorder as recorder_module
from krtr.back.security.audit.event_names import EventName
from krtr.back.security.audit.recorder import EventRecorder
from krtr.back.security.crypto.config import CryptoEnvironmentVariable
from krtr.back.security.oidc.config import OidcEnvironmentVariable
from krtr.back.web import app as app_module
from krtr.back.web.app import create_app
from krtr.back.web.chat.agent import AgentChatResponder
from krtr.back.web.chat.responder import StubChatResponder
from krtr.back.web.config import WebConfig, WebEnvironment, WebEnvironmentVariable
from krtr.database.neon import config as neon_config_module
from krtr.database.neon.config import NeonEnvironmentVariable
from tests.back.security.audit.fakes import InMemoryRecorder, refuse_to_open_neon


@pytest.fixture
def served_environment(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Isolates create_served_app from the developer's .env, its keys and secrets, and Neon."""
    monkeypatch.setattr(app_module, "load_dotenv", lambda: None)
    monkeypatch.setattr(neon_config_module, "load_dotenv", lambda: None)
    monkeypatch.delenv(NeonEnvironmentVariable.CONNECTION_STRING, raising=False)
    monkeypatch.setattr(recorder_module, "NeonClient", refuse_to_open_neon)
    monkeypatch.setattr(app_module, "NeonClient", refuse_to_open_neon)
    for variable in (*CryptoEnvironmentVariable, *OidcEnvironmentVariable):
        monkeypatch.delenv(variable, raising=False)
    return monkeypatch


def configure_login(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gives the served app what its login needs, with a stand-in Neon client."""
    monkeypatch.setenv(OidcEnvironmentVariable.CLIENT_SECRET, "test-client-secret")
    monkeypatch.setenv(CryptoEnvironmentVariable.TOKENS_KEY, base64.b64encode(b"t" * 32).decode())
    configure_chat(monkeypatch)  # Also stands in for the sessions' Neon client, unused here.


class StandInNeonClient:
    """Stands in for NeonClient where the test never queries: it opens no connection."""

    def __init__(self, config: object = None) -> None:
        """Accepts the config a real client would connect with, and ignores it."""
        self.config = config


def configure_chat(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gives the served app what its chat needs, with stand-in Neon clients."""
    monkeypatch.setenv(NeonEnvironmentVariable.CONNECTION_STRING, "postgresql://test/test")
    monkeypatch.setenv(CryptoEnvironmentVariable.MESSAGES_KEY, base64.b64encode(b"m" * 32).decode())
    monkeypatch.setattr(app_module, "NeonClient", StandInNeonClient)
    monkeypatch.setattr(message_store_module, "NeonClient", StandInNeonClient)


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
    configure_login(served_environment)

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


def test_served_app_refuses_to_start_in_production_without_login_settings(
    served_environment: pytest.MonkeyPatch,
) -> None:
    """Production without the OIDC client secret must fail fast, naming it."""
    served_environment.setenv(WebEnvironmentVariable.ENVIRONMENT, WebEnvironment.PRODUCTION)
    served_environment.setattr(EventRecorder, "from_environment", lambda: InMemoryRecorder())

    with pytest.raises(ValueError, match=OidcEnvironmentVariable.CLIENT_SECRET.value):
        app_module.create_served_app()


def test_served_app_refuses_to_start_in_production_without_the_tokens_key(
    served_environment: pytest.MonkeyPatch,
) -> None:
    """Sessions cannot store tokens without their key: production must not start."""
    served_environment.setenv(WebEnvironmentVariable.ENVIRONMENT, WebEnvironment.PRODUCTION)
    served_environment.setattr(EventRecorder, "from_environment", lambda: InMemoryRecorder())
    served_environment.setenv(OidcEnvironmentVariable.CLIENT_SECRET, "test-client-secret")

    with pytest.raises(ValueError, match=CryptoEnvironmentVariable.TOKENS_KEY.value):
        app_module.create_served_app()


def test_served_app_without_login_answers_503_on_login_routes(
    served_environment: pytest.MonkeyPatch,
) -> None:
    """Development without Keycloak keeps the app up, and says login is unavailable."""
    served_environment.setenv(WebEnvironmentVariable.ENVIRONMENT, WebEnvironment.DEVELOPMENT)

    response = TestClient(app_module.create_served_app()).get("/auth/login", follow_redirects=False)

    assert response.status_code == 503
    assert response.json()["error"] == "auth_unavailable"


def test_served_app_sends_logins_to_keycloak_when_configured(
    served_environment: pytest.MonkeyPatch,
) -> None:
    """With its settings, the served app's /auth/login redirects to the krtr realm."""
    served_environment.setenv(WebEnvironmentVariable.ENVIRONMENT, WebEnvironment.PRODUCTION)
    served_environment.setattr(EventRecorder, "from_environment", lambda: InMemoryRecorder())
    configure_login(served_environment)

    response = TestClient(app_module.create_served_app()).get("/auth/login", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"].startswith(
        "http://localhost:8080/realms/krtr/protocol/openid-connect/auth?"
    )


def test_served_app_answers_the_chat_with_the_engine_in_production(
    served_environment: pytest.MonkeyPatch,
) -> None:
    """Production chats with the conversation engine of krtr/back/ia/, not the placeholder."""
    served_environment.setenv(WebEnvironmentVariable.ENVIRONMENT, WebEnvironment.PRODUCTION)
    served_environment.setattr(EventRecorder, "from_environment", lambda: InMemoryRecorder())
    configure_login(served_environment)

    served_app = app_module.create_served_app()

    assert isinstance(served_app.state.chat_responder, AgentChatResponder)


def test_served_app_refuses_to_start_in_production_without_the_messages_key(
    served_environment: pytest.MonkeyPatch,
) -> None:
    """Chat text must be stored encrypted (§3.6): no key, no production app."""
    served_environment.setenv(WebEnvironmentVariable.ENVIRONMENT, WebEnvironment.PRODUCTION)
    served_environment.setattr(EventRecorder, "from_environment", lambda: InMemoryRecorder())
    configure_login(served_environment)
    served_environment.delenv(CryptoEnvironmentVariable.MESSAGES_KEY)

    with pytest.raises(ValueError, match=CryptoEnvironmentVariable.MESSAGES_KEY.value):
        app_module.create_served_app()


def test_served_app_answers_the_placeholder_in_development_without_neon(
    served_environment: pytest.MonkeyPatch,
) -> None:
    """Development without Neon keeps the chat usable with the D15 placeholder."""
    served_environment.setenv(WebEnvironmentVariable.ENVIRONMENT, WebEnvironment.DEVELOPMENT)

    served_app = app_module.create_served_app()

    assert isinstance(served_app.state.chat_responder, StubChatResponder)
