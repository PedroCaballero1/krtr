"""Tests the security-headers middleware, through the assembled FastAPI app."""

from fastapi.testclient import TestClient

from krtr.back.security.headers.config import HeadersConfig
from krtr.back.security.headers.middleware import build_content_security_policy
from krtr.back.web.app import create_app
from krtr.back.web.config import WebConfig


def make_client(auth_origin: str = "https://auth.example.com") -> TestClient:
    """Builds a TestClient for the app with a fixed auth_origin, for stable assertions."""
    return TestClient(create_app(WebConfig(), HeadersConfig(auth_origin=auth_origin)))


def test_response_carries_every_static_security_header() -> None:
    """Verifies each hardening header from §4.2 is present with its exact value."""
    response = make_client().get("/healthz")

    assert response.headers["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["Permissions-Policy"] == "microphone=(self), camera=(), geolocation=()"
    assert response.headers["Cross-Origin-Opener-Policy"] == "same-origin"


def test_content_security_policy_includes_the_configured_auth_origin() -> None:
    """Verifies the CSP's form-action allows the configured Keycloak origin."""
    response = make_client(auth_origin="https://auth.krtr.example").get("/healthz")

    csp = response.headers["Content-Security-Policy"]
    assert "form-action 'self' https://auth.krtr.example" in csp
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "object-src 'none'" in csp


def test_api_routes_get_cache_control_no_store() -> None:
    """Verifies /api/* responses are never cached, while other routes are unaffected."""
    client = make_client()

    api_response = client.get("/api/whatever")
    healthz_response = client.get("/healthz")

    assert api_response.headers["Cache-Control"] == "no-store"
    assert "Cache-Control" not in healthz_response.headers


def test_server_header_is_never_leaked() -> None:
    """Verifies the Server header (which would reveal the ASGI server) is stripped."""
    response = make_client().get("/healthz")

    assert "Server" not in response.headers


def test_build_content_security_policy_is_a_single_semicolon_separated_string() -> None:
    """Verifies the CSP builder's exact directive set and order, independent of the app."""
    csp = build_content_security_policy("https://auth.example.com")

    assert csp == (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "img-src 'self' data:; "
        "media-src 'self' blob:; "
        "connect-src 'self'; "
        "form-action 'self' https://auth.example.com; "
        "frame-ancestors 'none'; "
        "base-uri 'none'; "
        "object-src 'none'"
    )
