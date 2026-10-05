"""Tests SessionService against G15: 5 minutes idle, 30 at most, one session per customer."""

from datetime import timedelta

import pytest

from krtr.back.security.sessions.artifacts import SessionEndReason
from krtr.back.security.sessions.errors import SessionRejected
from krtr.back.security.sessions.service import SessionService, hash_session_token
from tests.back.security.oidc.fakes import START, FakeClock
from tests.back.security.sessions.fakes import (
    FakeRefresher,
    InMemorySessionStore,
    tokens_expiring_at,
)

CUSTOMER = "12345678"


def build() -> tuple[SessionService, InMemorySessionStore, FakeClock, FakeRefresher]:
    """Builds a service on an in-memory store, a fake clock and a fake refresher."""
    clock = FakeClock()
    store = InMemorySessionStore()
    refresher = FakeRefresher(clock)
    return SessionService(store, refresher, clock=clock), store, clock, refresher


def login(service: SessionService, clock: FakeClock, customer: str = CUSTOMER) -> str:
    """Logs a customer in with 5-minute tokens and returns the session cookie value."""
    return service.start(customer, tokens_expiring_at(clock() + timedelta(minutes=5))).token


def rejection(service: SessionService, token: str | None) -> SessionEndReason:
    """Returns why a cookie is rejected (fails if it is accepted)."""
    with pytest.raises(SessionRejected) as raised:
        service.authenticate(token)
    return raised.value.reason


def test_the_cookie_is_256_random_bits_and_only_its_hash_is_stored() -> None:
    """A database leak must not hand out usable cookies."""
    service, store, clock, _ = build()

    token = login(service, clock)

    assert len(token) >= 43  # 32 bytes in base64url.
    assert token not in store.sessions and hash_session_token(token) in store.sessions


def test_a_new_session_reports_both_deadlines() -> None:
    """The frontend warns 30 s before each deadline, so it needs both (D13)."""
    service, _, clock, _ = build()

    status = service.start(CUSTOMER, tokens_expiring_at(clock() + timedelta(minutes=5))).status

    assert (status.idle_expires_at, status.absolute_expires_at) == (
        START.replace(minute=5),
        START.replace(minute=30),
    )


def test_the_session_closes_at_exactly_5_idle_minutes() -> None:
    """G15: 4:59 without activity is fine; 5:00 ends the session."""
    service, _, clock, _ = build()
    token = login(service, clock)

    clock.advance(minutes=4, seconds=59)
    service.authenticate(token)
    clock.advance(seconds=1)

    assert rejection(service, token) == SessionEndReason.IDLE
    assert rejection(service, token) == SessionEndReason.REVOKED  # It stays closed.


def test_activity_extends_the_idle_limit_but_never_the_30_minute_one() -> None:
    """G15: an active customer is still logged out 30 minutes after logging in."""
    service, _, clock, _ = build()
    token = login(service, clock)

    for _ in range(7):  # Active every 4 minutes, until minute 28.
        clock.advance(minutes=4)
        service.record_activity(service.authenticate(token))
    clock.advance(minutes=1, seconds=59)
    service.authenticate(token)
    clock.advance(seconds=1)

    assert rejection(service, token) == SessionEndReason.ABSOLUTE


def test_the_idle_deadline_never_passes_the_absolute_one() -> None:
    """At minute 28, activity cannot promise 5 more minutes: the session ends at 30."""
    service, _, clock, _ = build()
    token = login(service, clock)
    for _ in range(7):
        clock.advance(minutes=4)
        status = service.record_activity(service.authenticate(token))

    assert status.idle_expires_at == status.absolute_expires_at == START.replace(minute=30)


def test_a_second_login_closes_the_first_session() -> None:
    """G15: one session per customer; the newest wins."""
    service, _, clock, _ = build()
    first = login(service, clock)

    second = service.start(CUSTOMER, tokens_expiring_at(clock() + timedelta(minutes=5)))

    assert second.replaced_sessions == 1
    assert rejection(service, first) == SessionEndReason.REVOKED
    assert service.authenticate(second.token).customer_id == CUSTOMER


def test_another_customers_login_does_not_touch_this_session() -> None:
    """Only the same customer's sessions are replaced."""
    service, _, clock, _ = build()
    token = login(service, clock)

    other = service.start("87654321", tokens_expiring_at(clock() + timedelta(minutes=5)))

    assert other.replaced_sessions == 0 and service.authenticate(token).customer_id == CUSTOMER


@pytest.mark.parametrize("token", [None, "", "forged-or-tampered-cookie"])
def test_missing_or_unknown_cookies_are_rejected(token: str | None) -> None:
    """A tampered cookie is just an unknown one: it never opens a session."""
    service, _, clock, _ = build()
    login(service, clock)

    assert rejection(service, token) == SessionEndReason.UNKNOWN


def test_tokens_are_refreshed_when_less_than_a_minute_is_left() -> None:
    """Refreshing in time keeps the access token valid and Keycloak's session alive."""
    service, store, clock, refresher = build()
    token = login(service, clock)

    clock.advance(minutes=3)
    service.record_activity(service.authenticate(token))
    assert refresher.calls == []
    clock.advance(minutes=1, seconds=1)  # 59 s left.
    service.record_activity(service.authenticate(token))

    assert refresher.calls == ["refresh-0"]
    assert store.find(hash_session_token(token)).tokens.refresh_token == "refresh-1"


def test_a_refused_refresh_ends_the_session() -> None:
    """If Keycloak's session is gone, krtr's session must not outlive it."""
    service, _, clock, refresher = build()
    token = login(service, clock)
    refresher.refuse = True
    clock.advance(minutes=4, seconds=30)

    with pytest.raises(SessionRejected) as raised:
        service.record_activity(service.authenticate(token))

    assert raised.value.reason == SessionEndReason.REVOKED
    assert rejection(service, token) == SessionEndReason.REVOKED


def test_logout_ends_the_session() -> None:
    """After logout the cookie no longer opens anything."""
    service, _, clock, _ = build()
    token = login(service, clock)

    service.end(service.authenticate(token))

    assert rejection(service, token) == SessionEndReason.REVOKED
