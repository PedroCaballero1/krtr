"""Tests GET /api/me and POST /api/session/activity (task 4.4) and how sessions are rejected."""

import pytest

from krtr.back.security.audit.event_names import EventName
from krtr.back.security.sessions.config import SESSION_COOKIE_NAME
from krtr.back.security.sessions.service import hash_session_token
from tests.back.security.oidc.fakes import START
from tests.back.web.fakes import CUSTOMER, WebHarness, build_harness


@pytest.fixture
def web() -> WebHarness:
    """Builds the app with fake Keycloak, sessions, events and clock."""
    return build_harness()


def test_me_reports_the_customer_and_both_deadlines(web: WebHarness) -> None:
    """The frontend needs both deadlines to warn 30 s before each (D13)."""
    web.log_in()

    response = web.client.get("/api/me")

    assert response.status_code == 200
    assert response.json() == {
        "customer_id": CUSTOMER,
        "idle_expires_at": START.replace(minute=5).isoformat().replace("+00:00", "Z"),
        "absolute_expires_at": START.replace(minute=30).isoformat().replace("+00:00", "Z"),
    }


def test_me_is_not_activity(web: WebHarness) -> None:
    """Polling /api/me must not keep an idle session alive; only explicit activity does."""
    web.log_in()
    web.clock.advance(minutes=4)
    web.client.get("/api/me")
    web.clock.advance(minutes=1)

    response = web.client.get("/api/me")

    assert response.status_code == 401
    assert response.json()["error"] == "session_expired_idle"


def test_activity_pushes_the_idle_deadline_back(web: WebHarness) -> None:
    """A customer active every few minutes stays logged in past the first 5 minutes."""
    web.log_in()
    web.clock.advance(minutes=4)

    activity = web.client.post("/api/session/activity")
    web.clock.advance(minutes=4)
    me = web.client.get("/api/me")

    assert activity.status_code == 200
    assert activity.json()["idle_expires_at"].startswith("2026-10-02T12:09:00")
    assert me.status_code == 200


def test_activity_never_moves_the_absolute_deadline(web: WebHarness) -> None:
    """However active, a session ends 30 minutes after login (G15)."""
    web.log_in()
    for _ in range(7):
        web.clock.advance(minutes=4)
        assert web.client.post("/api/session/activity").status_code == 200
    web.clock.advance(minutes=2)

    response = web.client.post("/api/session/activity")

    assert response.status_code == 401
    assert response.json() == {
        "error": "session_expired_absolute",
        "message_key": "session_expired_absolute_message",
    }
    assert web.recorded()[-2:] == ["unauthorized_request", "session_expired_absolute"]


def test_an_idle_session_is_rejected_cleared_and_recorded(web: WebHarness) -> None:
    """5 minutes idle: 401 with the idle message, the cookie cleared, both events recorded."""
    token = web.log_in()
    web.clock.advance(minutes=5)

    response = web.client.get("/api/me")

    assert response.status_code == 401
    assert response.json() == {
        "error": "session_expired_idle",
        "message_key": "session_expired_idle_message",
    }
    assert "Max-Age=0" in response.headers["set-cookie"]
    assert web.store.find(hash_session_token(token)).revoked_at == web.clock()
    assert web.properties_of(EventName.UNAUTHORIZED_REQUEST) == {
        "path": "/api/me",
        "reason": "idle",
    }
    assert web.properties_of(EventName.SESSION_EXPIRED_IDLE) == {"customer_id": CUSTOMER}


@pytest.mark.parametrize("cookie", [None, "forged-session-id"])
def test_a_request_without_a_real_session_is_401(web: WebHarness, cookie: str | None) -> None:
    """No cookie, or one that opens no session, answers unauthorized and records it."""
    web.log_in()
    web.client.cookies.clear()
    if cookie is not None:
        web.client.cookies.set(SESSION_COOKIE_NAME, cookie)

    response = web.client.get("/api/me")

    assert response.status_code == 401
    assert response.json() == {"error": "unauthorized", "message_key": "unauthorized"}
    assert web.properties_of(EventName.UNAUTHORIZED_REQUEST) == {
        "path": "/api/me",
        "reason": "unknown",
    }
    assert "session_expired_idle" not in web.recorded()


def test_activity_refreshes_tokens_that_are_about_to_expire(web: WebHarness) -> None:
    """The access token (5 minutes) is renewed by activity, so a 30-minute session keeps working."""
    token = web.log_in()
    first_tokens = web.store.find(hash_session_token(token)).tokens
    web.clock.advance(minutes=4, seconds=30)

    web.client.post("/api/session/activity")

    assert web.refresher.calls == [first_tokens.refresh_token]
    assert web.store.find(hash_session_token(token)).tokens != first_tokens


def test_a_refused_refresh_ends_the_session(web: WebHarness) -> None:
    """If Keycloak ended its session (e.g. an admin disabled the user), krtr's ends too."""
    web.log_in()
    web.refresher.refuse = True
    web.clock.advance(minutes=4, seconds=30)

    response = web.client.post("/api/session/activity")

    assert response.status_code == 401
    assert response.json()["error"] == "unauthorized"
    assert web.client.get("/api/me").status_code == 401
