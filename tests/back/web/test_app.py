"""Tests create_app(): health, docs gating by environment, and the SPA fallback."""

from pathlib import Path

from fastapi.testclient import TestClient

from krtr.back.web.app import create_app
from krtr.back.web.config import WebConfig, WebEnvironment


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
