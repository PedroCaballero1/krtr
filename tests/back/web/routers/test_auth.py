"""Tests /auth/login, /auth/callback and /auth/logout (task 4.3) against fake Keycloak."""

from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from krtr.back.security.audit.event_names import EventName
from krtr.back.security.oidc.config import LOGIN_COOKIE_NAME
from krtr.back.security.oidc.errors import LoginFailureReason
from krtr.back.security.sessions.config import SESSION_COOKIE_NAME
from krtr.back.security.sessions.service import hash_session_token
from tests.back.web.fakes import AUTHORIZE_URL, CUSTOMER, WebHarness, build_harness


@pytest.fixture
def web() -> WebHarness:
    """Builds the app with fake Keycloak, sessions, events and clock."""
    return build_harness()


def set_cookie_header(response_headers: list[str], name: str) -> str:
    """Returns the Set-Cookie header that sets or clears one cookie (fails if absent)."""
    return next(header for header in response_headers if header.startswith(f"{name}="))


def start_login(web: WebHarness, lang: str = "es") -> str:
    """Calls /auth/login and returns the state of the login it started."""
    response = web.client.get(f"/auth/login?lang={lang}", follow_redirects=False)
    assert response.status_code == 302
    return parse_qs(urlsplit(response.headers["location"]).query)["state"][0]


def callback(web: WebHarness, query: str) -> httpx.Response:
    """Calls /auth/callback with the given query string, without following redirects."""
    return web.client.get(f"/auth/callback?{query}", follow_redirects=False)


def test_login_redirects_to_keycloak_with_an_encrypted_login_cookie(web: WebHarness) -> None:
    """The secrets of the login travel only encrypted, in a __Host- Lax cookie for 10 minutes."""
    response = web.client.get("/auth/login?lang=pt-BR", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"].startswith(AUTHORIZE_URL)
    assert parse_qs(urlsplit(response.headers["location"]).query)["ui_locales"] == ["pt-BR"]
    header = set_cookie_header(response.headers.get_list("set-cookie"), LOGIN_COOKIE_NAME)
    for flag in ("HttpOnly", "Secure", "Path=/", "SameSite=lax", "Max-Age=600"):
        assert flag in header
    assert "Domain" not in header
    login_state = web.oidc.started[0]
    for secret in (login_state.state, login_state.nonce, login_state.code_verifier):
        assert secret not in header
    assert web.recorded() == ["auth_login_started"]
    assert web.properties_of(EventName.AUTH_LOGIN_STARTED) == {"language": "pt-BR"}


def test_login_rejects_a_language_krtr_does_not_offer(web: WebHarness) -> None:
    """Only es and pt-BR exist (G14); anything else is a 422, not a Keycloak redirect."""
    response = web.client.get("/auth/login?lang=fr", follow_redirects=False)

    assert response.status_code == 422
    assert web.oidc.started == []


def test_a_valid_callback_opens_a_session_and_sends_the_customer_to_the_app(
    web: WebHarness,
) -> None:
    """The session cookie is __Host-, Strict and HttpOnly; the login cookie is cleared."""
    state = start_login(web)

    response = callback(web, f"code=abc&state={state}")

    assert response.status_code == 302
    assert response.headers["location"] == "/app"
    headers = response.headers.get_list("set-cookie")
    session_header = set_cookie_header(headers, SESSION_COOKIE_NAME)
    for flag in ("HttpOnly", "Secure", "Path=/", "SameSite=strict", "Max-Age=1800"):
        assert flag in session_header
    assert "Max-Age=0" in set_cookie_header(headers, LOGIN_COOKIE_NAME)
    token = response.cookies[SESSION_COOKIE_NAME]
    assert web.store.find(hash_session_token(token)).customer_id == CUSTOMER
    assert web.oidc.exchanged_codes == ["abc"]
    assert web.recorded() == ["auth_login_started", "auth_login_succeeded", "session_created"]


def test_the_session_cookie_holds_no_token_from_keycloak(web: WebHarness) -> None:
    """The browser only ever holds the session id, never an OIDC token (BFF, §3.2)."""
    token = web.log_in()

    tokens = web.store.find(hash_session_token(token)).tokens
    assert token not in (tokens.access_token, tokens.refresh_token, tokens.id_token)


@pytest.mark.parametrize(
    ("query", "reason"),
    [
        ("code=abc&state=forged", LoginFailureReason.STATE_MISMATCH),
        ("code=abc", LoginFailureReason.STATE_MISMATCH),
        ("error=access_denied&state={state}", LoginFailureReason.PROVIDER_ERROR),
        ("state={state}", LoginFailureReason.MISSING_CODE),
    ],
)
def test_a_callback_that_does_not_answer_this_login_is_rejected(
    web: WebHarness, query: str, reason: LoginFailureReason
) -> None:
    """A forged state (CSRF on the login), Keycloak's error or a missing code never log in."""
    state = start_login(web)

    response = callback(web, query.format(state=state))

    assert response.status_code == 400
    assert response.json() == {"error": "login_failed", "message_key": "login_failed"}
    assert web.oidc.exchanged_codes == []
    assert web.store.sessions == {}
    assert "Max-Age=0" in set_cookie_header(
        response.headers.get_list("set-cookie"), LOGIN_COOKIE_NAME
    )
    assert web.properties_of(EventName.AUTH_LOGIN_FAILED) == {"reason": reason.value}


def test_a_callback_without_the_login_cookie_is_rejected(web: WebHarness) -> None:
    """A callback in a browser that did not start the login (login CSRF) is refused."""
    state = start_login(web)
    web.client.cookies.clear()

    response = callback(web, f"code=abc&state={state}")

    assert response.status_code == 400
    assert web.properties_of(EventName.AUTH_LOGIN_FAILED) == {
        "reason": LoginFailureReason.MISSING_LOGIN_COOKIE.value
    }


def test_a_callback_after_the_login_cookie_expired_is_rejected(web: WebHarness) -> None:
    """A login left open for more than 10 minutes must be started again."""
    state = start_login(web)
    web.clock.advance(minutes=10)

    response = callback(web, f"code=abc&state={state}")

    assert response.status_code == 400
    assert web.properties_of(EventName.AUTH_LOGIN_FAILED) == {
        "reason": LoginFailureReason.EXPIRED_LOGIN.value
    }


def test_a_tampered_login_cookie_is_rejected(web: WebHarness) -> None:
    """The login cookie is authenticated encryption: a changed value is a forged one."""
    state = start_login(web)
    web.client.cookies.set(LOGIN_COOKIE_NAME, "AAAA" + web.client.cookies[LOGIN_COOKIE_NAME][4:])

    response = callback(web, f"code=abc&state={state}")

    assert response.status_code == 400
    assert web.properties_of(EventName.AUTH_LOGIN_FAILED) == {
        "reason": LoginFailureReason.INVALID_LOGIN_COOKIE.value
    }


def test_a_code_keycloak_rejects_does_not_log_in(web: WebHarness) -> None:
    """A failed token exchange or ID token check (e.g. wrong nonce) answers 400, no session."""
    web.oidc.rejection = LoginFailureReason.NONCE_MISMATCH
    state = start_login(web)

    response = callback(web, f"code=abc&state={state}")

    assert response.status_code == 400
    assert web.store.sessions == {}
    assert web.properties_of(EventName.AUTH_LOGIN_FAILED) == {
        "reason": LoginFailureReason.NONCE_MISMATCH.value
    }


def test_a_used_login_cookie_is_gone_so_the_callback_cannot_be_replayed(web: WebHarness) -> None:
    """After a successful callback the browser no longer holds the login's secrets."""
    state = start_login(web)
    assert callback(web, f"code=abc&state={state}").status_code == 302

    response = callback(web, f"code=abc&state={state}")

    assert LOGIN_COOKIE_NAME not in web.client.cookies
    assert response.status_code == 400
    assert web.properties_of(EventName.AUTH_LOGIN_FAILED) == {
        "reason": LoginFailureReason.MISSING_LOGIN_COOKIE.value
    }


def test_a_new_login_closes_the_customers_previous_session(web: WebHarness) -> None:
    """One session per customer (G15): the first browser is logged out."""
    first_token = web.log_in()

    web.log_in()

    assert web.store.find(hash_session_token(first_token)).revoked_at is not None
    assert web.properties_of(EventName.SESSION_REVOKED_BY_NEW_LOGIN) == {
        "customer_id": CUSTOMER,
        "replaced_sessions": 1,
    }


def test_the_first_login_records_no_revocation(web: WebHarness) -> None:
    """session_revoked_by_new_login is recorded only when a session was really closed."""
    web.log_in()

    assert "session_revoked_by_new_login" not in web.recorded()


def test_logout_ends_the_session_here_and_in_keycloak(web: WebHarness) -> None:
    """After logout the old cookie opens nothing, and Keycloak's session was ended too."""
    token = web.log_in()
    tokens = web.store.find(hash_session_token(token)).tokens

    response = web.post("/auth/logout")

    assert response.status_code == 204
    assert "Max-Age=0" in set_cookie_header(
        response.headers.get_list("set-cookie"), SESSION_COOKIE_NAME
    )
    assert web.oidc.ended_sessions == [tokens]
    assert web.properties_of(EventName.AUTH_LOGOUT) == {"customer_id": CUSTOMER}
    web.client.cookies.set(SESSION_COOKIE_NAME, token)
    assert web.client.get("/api/me").status_code == 401


def test_logout_without_a_session_is_401(web: WebHarness) -> None:
    """Logout is a session route: no session, nothing to end, and Keycloak is not called."""
    response = web.post("/auth/logout")

    assert response.status_code == 401
    assert web.oidc.ended_sessions == []
