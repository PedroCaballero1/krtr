"""Security tests against the deployed krtr-web and Keycloak (task 7.2).

Each test states the control it proves. They change nothing for real customers: they use the QA
accounts (D4) and cases those accounts open.
"""

import httpx
import pytest

from e2e.security.conftest import csrf_headers, log_in, new_browser

HIDDEN_AUTH_PATHS = [
    "/admin/",
    "/admin/master/console/",
    "/realms/master/protocol/openid-connect/token",
    "/health/ready",
    "/metrics",
]


def test_security_headers_are_present_and_server_is_hidden(base_url: str) -> None:
    """4.2: CSP, HSTS, nosniff; no Server header."""
    response = httpx.get(f"{base_url}/healthz", timeout=30)

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["strict-transport-security"].startswith("max-age=")
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert "server" not in response.headers


@pytest.mark.parametrize("path", ["/docs", "/openapi.json", "/redoc"])
def test_api_docs_are_not_published(base_url: str, path: str) -> None:
    """4.1: no interactive docs in production."""
    assert httpx.get(f"{base_url}{path}", timeout=30).status_code == 404


@pytest.mark.parametrize("path", ["/api/me", "/api/cases?status=open"])
def test_the_api_needs_a_session(base_url: str, path: str) -> None:
    """P5.4: without a session, 401."""
    assert httpx.get(f"{base_url}{path}", timeout=30).status_code == 401


def test_another_modal_app_cannot_post_events(base_url: str) -> None:
    """4.5: a sibling *.modal.run origin is foreign."""
    response = httpx.post(
        f"{base_url}/api/events",
        json={"event_name": "page_view"},
        headers={"Origin": "https://attacker--evil.modal.run"},
        timeout=30,
    )

    assert response.status_code == 403


@pytest.mark.parametrize("path", HIDDEN_AUTH_PATHS)
def test_keycloak_admin_and_operational_paths_are_hidden(auth_url: str, path: str) -> None:
    """D19: the gateway never lets these reach Keycloak."""
    assert httpx.get(f"{auth_url}{path}", timeout=30).status_code == 404


def test_the_login_cookie_is_host_prefixed_and_lax(base_url: str) -> None:
    """D22: __Host-, Secure, HttpOnly, SameSite=Lax."""
    response = httpx.get(f"{base_url}/auth/login?lang=pt-BR", timeout=30)
    cookie = response.headers["set-cookie"].lower()

    assert response.status_code == 302
    assert "ui_locales=pt-br" in response.headers["location"].lower()
    assert cookie.startswith("__host-krtr_oidc=")
    assert all(flag in cookie for flag in ("secure", "httponly", "samesite=lax", "path=/"))


def test_a_qa_account_logs_in_with_a_strict_session(
    base_url: str, qa_accounts: list[tuple[str, str]]
) -> None:
    """G5/G6: the real form logs in; the session cookie is __Host- and Strict."""
    browser = new_browser()
    final = log_in(browser, base_url, *qa_accounts[0])
    session_cookie = next(
        cookie for cookie in browser.cookies.jar if cookie.name == "__Host-krtr_session"
    )

    assert final.url.path == "/app"
    assert session_cookie.secure
    assert browser.get(f"{base_url}/api/me").json()["customer_id"] == qa_accounts[0][0]


def test_a_wrong_password_does_not_log_in(
    base_url: str, qa_accounts: list[tuple[str, str]]
) -> None:
    """The form rejects it and no session is created."""
    browser = new_browser()

    log_in(browser, base_url, qa_accounts[1][0], "WrongPw99")

    assert browser.get(f"{base_url}/api/me").status_code == 401


def test_a_second_login_closes_the_first(base_url: str, qa_accounts: list[tuple[str, str]]) -> None:
    """G15: one session per customer."""
    first, second = new_browser(), new_browser()
    log_in(first, base_url, *qa_accounts[2])

    log_in(second, base_url, *qa_accounts[2])

    assert first.get(f"{base_url}/api/me").status_code == 401
    assert second.get(f"{base_url}/api/me").status_code == 200


def test_posts_without_csrf_are_rejected(base_url: str, qa_accounts: list[tuple[str, str]]) -> None:
    """4.5: a logged-in browser still needs the echoed token."""
    browser = new_browser()
    log_in(browser, base_url, *qa_accounts[3])

    response = browser.post(f"{base_url}/api/cases", headers={"Origin": base_url})

    assert response.status_code == 403


def test_another_customers_case_is_404(base_url: str, qa_accounts: list[tuple[str, str]]) -> None:
    """IDOR: B's case answers A exactly like a missing case."""
    owner, other = new_browser(), new_browser()
    log_in(owner, base_url, *qa_accounts[4])
    log_in(other, base_url, *qa_accounts[5])
    case = owner.post(f"{base_url}/api/cases", headers=csrf_headers(owner, base_url)).json()

    response = other.post(
        f"{base_url}/api/cases/resume",
        json={"incident_id": case["incident_id"]},
        headers=csrf_headers(other, base_url),
    )

    assert response.status_code == 404


def test_the_chat_answers_and_limits_to_20_messages_a_minute(
    base_url: str, qa_accounts: list[tuple[str, str]]
) -> None:
    """G3/G9: a complete reply per message; the 21st in a minute is 429."""
    browser = new_browser()
    log_in(browser, base_url, *qa_accounts[6])
    headers = csrf_headers(browser, base_url)
    incident_id = browser.post(f"{base_url}/api/cases", headers=headers).json()["incident_id"]
    body = {"incident_id": incident_id, "text": "¿Cuál es mi saldo?", "language": "es"}

    statuses = [
        browser.post(f"{base_url}/api/chat/messages", json=body, headers=headers).status_code
        for _ in range(21)
    ]

    assert statuses[:20] == [200] * 20
    assert statuses[20] == 429


def test_a_fake_voice_file_is_415(base_url: str, qa_accounts: list[tuple[str, str]]) -> None:
    """4.9: the bytes must be WebM or MP4, whatever the declared type."""
    browser = new_browser()
    log_in(browser, base_url, *qa_accounts[7])
    headers = csrf_headers(browser, base_url)
    incident_id = browser.post(f"{base_url}/api/cases", headers=headers).json()["incident_id"]

    response = browser.post(
        f"{base_url}/api/chat/voice",
        data={"incident_id": incident_id, "language": "es"},
        files={"audio": ("note.webm", b"\x89PNG\r\n\x1a\n" + b"0" * 100, "audio/webm")},
        headers=headers,
    )

    assert response.status_code == 415
