"""Tests the CSRF protection of krtr-web's routes (task 4.5).

Acceptance: without the header, with another token, or from another origin (even another
*.modal.run app), a state-changing request answers 403 and records `csrf_rejected`.
"""

import pytest

from krtr.back.security.audit.event_names import EventName
from krtr.back.security.csrf.config import CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from tests.back.web.fakes import APP_ORIGIN, WebHarness, build_harness

STATE_CHANGING_ROUTES = ["/api/session/activity", "/auth/logout"]


@pytest.fixture
def web() -> WebHarness:
    """Builds the app with fake Keycloak, sessions, events and clock."""
    return build_harness()


def csrf_cookie_header(web: WebHarness) -> str:
    """Returns the Set-Cookie line of the CSRF cookie a fresh login sets."""
    web.client.get("/auth/login", follow_redirects=False)
    state = web.oidc.started[-1].state
    callback = web.client.get(f"/auth/callback?code=c&state={state}", follow_redirects=False)
    return next(
        line
        for line in callback.headers.get_list("set-cookie")
        if line.startswith(f"{CSRF_COOKIE_NAME}=")
    )


def test_login_sets_a_csrf_cookie_the_spa_can_read(web: WebHarness) -> None:
    """The SPA echoes the cookie, so it must not be HttpOnly; `__Host-` keeps siblings out."""
    cookie = csrf_cookie_header(web).lower()

    assert "secure" in cookie
    assert "path=/" in cookie
    assert "samesite=strict" in cookie
    assert "domain=" not in cookie
    assert "httponly" not in cookie


@pytest.mark.parametrize("path", STATE_CHANGING_ROUTES)
def test_the_spa_passes_both_checks(web: WebHarness, path: str) -> None:
    """Same origin and the echoed token: the request goes through."""
    web.log_in()

    assert web.post(path).status_code in (200, 204)


@pytest.mark.parametrize("path", STATE_CHANGING_ROUTES)
def test_without_the_header_the_request_is_rejected(web: WebHarness, path: str) -> None:
    """A cross-site form post carries the cookies but cannot add X-KRTR-CSRF."""
    web.log_in()

    response = web.client.post(path, headers={"Origin": APP_ORIGIN})

    assert response.status_code == 403
    assert response.json() == {"error": "csrf_rejected", "message_key": "csrf_rejected"}
    assert web.properties_of(EventName.CSRF_REJECTED) == {"path": path, "reason": "missing_token"}


@pytest.mark.parametrize("path", STATE_CHANGING_ROUTES)
def test_another_token_is_rejected(web: WebHarness, path: str) -> None:
    """A guessed token does not match the cookie the attacker cannot read."""
    web.log_in()

    response = web.client.post(
        path, headers={"Origin": APP_ORIGIN, CSRF_HEADER_NAME: "guessed-token"}
    )

    assert response.status_code == 403
    assert web.properties_of(EventName.CSRF_REJECTED)["reason"] == "token_mismatch"


@pytest.mark.parametrize("path", STATE_CHANGING_ROUTES)
def test_another_modal_app_is_rejected_even_with_the_token(web: WebHarness, path: str) -> None:
    """SameSite does not separate *.modal.run apps; the Origin check does."""
    web.log_in()
    token = web.client.cookies.get(CSRF_COOKIE_NAME)

    response = web.client.post(
        path,
        headers={"Origin": "https://attacker--evil.modal.run", CSRF_HEADER_NAME: token},
    )

    assert response.status_code == 403
    assert web.properties_of(EventName.CSRF_REJECTED)["reason"] == "foreign_origin"


def test_a_rejected_request_changes_nothing(web: WebHarness) -> None:
    """A forged logout must leave the session alive."""
    web.log_in()

    web.client.post("/auth/logout", headers={"Origin": "https://evil.example"})

    assert web.client.get("/api/me").status_code == 200
    assert web.oidc.ended_sessions == []


def test_without_a_session_the_answer_is_401_not_403(web: WebHarness) -> None:
    """A logged-out SPA must be sent back to the landing page, which only 401 does."""
    response = web.client.post("/api/session/activity", headers={"Origin": APP_ORIGIN})

    assert response.status_code == 401


def test_logout_clears_the_csrf_cookie(web: WebHarness) -> None:
    """The token dies with the session it protects."""
    web.log_in()

    response = web.post("/auth/logout")

    cleared = [
        line
        for line in response.headers.get_list("set-cookie")
        if line.startswith(f"{CSRF_COOKIE_NAME}=")
    ]
    assert len(cleared) == 1
    assert "max-age=0" in cleared[0].lower()


def test_an_expired_session_clears_the_csrf_cookie(web: WebHarness) -> None:
    """A 401 for an expired session also drops the token."""
    web.log_in()
    web.clock.advance(minutes=5)

    response = web.client.get("/api/me")

    assert any(
        line.startswith(f"{CSRF_COOKIE_NAME}=") for line in response.headers.get_list("set-cookie")
    )


def test_events_need_only_the_origin(web: WebHarness) -> None:
    """The landing page reports events before any session or CSRF cookie exists."""
    response = web.client.post(
        "/api/events", json={"event_name": "page_view"}, headers={"Origin": APP_ORIGIN}
    )

    assert response.status_code == 202


@pytest.mark.parametrize("origin", [None, "https://attacker--evil.modal.run"])
def test_events_from_another_origin_are_rejected(web: WebHarness, origin: str | None) -> None:
    """Another site must not be able to write into krtr's audit log."""
    headers = {"Origin": origin} if origin else {}

    response = web.client.post("/api/events", json={"event_name": "page_view"}, headers=headers)

    assert response.status_code == 403
    assert web.recorded() == ["csrf_rejected"]
