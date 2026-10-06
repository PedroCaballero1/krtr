"""Tests krtr-web's request limits (task 4.6).

Acceptance: the 21st chat message answers 429, the 601st request from one IP answers 429, and a
spoofed X-Forwarded-For, X-Real-IP or Forwarded header does not evade the limit (0.4a).
"""

import pytest

from krtr.back.security.audit.event_names import EventName
from krtr.back.security.rate_limit.config import RateLimitConfig
from tests.back.web.fakes import WebHarness, build_harness

SPOOFED_HEADERS = [
    {"X-Forwarded-For": "203.0.113.7"},
    {"X-Real-IP": "203.0.113.8"},
    {"Forwarded": "for=203.0.113.9"},
]


def send_text(web: WebHarness, incident_id: str) -> int:
    """Sends one chat message and returns the status code."""
    body = {"incident_id": incident_id, "text": "hola", "language": "es"}
    return web.post("/api/chat/messages", json=body).status_code


def test_the_21st_chat_message_in_a_minute_is_429() -> None:
    """G3: 20 messages per minute per customer, with Retry-After and an event."""
    web = build_harness()
    web.log_in()
    incident_id = web.post("/api/cases").json()["incident_id"]
    statuses = [send_text(web, incident_id) for _ in range(20)]

    response = web.post(
        "/api/chat/messages", json={"incident_id": incident_id, "text": "hola", "language": "es"}
    )

    assert statuses == [200] * 20
    assert response.status_code == 429
    assert response.json() == {"error": "rate_limited", "message_key": "chat_error_rate_limited"}
    assert 1 <= int(response.headers["Retry-After"]) <= 60
    assert web.properties_of(EventName.RATE_LIMIT_EXCEEDED)["scope"] == "chat"


def test_the_chat_limit_is_per_customer() -> None:
    """Another customer keeps chatting while the first one waits."""
    web = build_harness(rate_limit_config=RateLimitConfig(chat_per_customer=1))
    web.log_in("A")
    a_case = web.post("/api/cases").json()["incident_id"]
    send_text(web, a_case)
    assert send_text(web, a_case) == 429
    web.log_in("B")

    assert send_text(web, web.post("/api/cases").json()["incident_id"]) == 200


def test_the_601st_request_from_one_ip_is_429() -> None:
    """D6: 600 requests per minute per IP, on the whole site."""
    web = build_harness()
    statuses = [web.client.get("/healthz").status_code for _ in range(600)]

    response = web.client.get("/healthz")

    assert statuses == [200] * 600
    assert response.status_code == 429
    assert web.properties_of(EventName.RATE_LIMIT_EXCEEDED)["scope"] == "ip"


@pytest.mark.parametrize("spoofed", SPOOFED_HEADERS)
def test_a_spoofed_client_ip_header_does_not_evade_the_limit(spoofed: dict[str, str]) -> None:
    """Modal passes these headers through untouched (0.4a); only the peer address counts."""
    web = build_harness(rate_limit_config=RateLimitConfig(per_ip=3))
    for _ in range(3):
        web.client.get("/healthz")

    response = web.client.get("/healthz", headers=spoofed)

    assert response.status_code == 429


def test_the_session_limit_applies_to_the_api() -> None:
    """A script reusing one session is stopped on /api/* even below the IP limit."""
    web = build_harness(rate_limit_config=RateLimitConfig(per_session=5))
    web.log_in()
    statuses = [web.client.get("/api/me").status_code for _ in range(5)]

    response = web.client.get("/api/me")

    assert statuses == [200] * 5
    assert response.status_code == 429
    assert response.json()["message_key"] == "rate_limited"
    assert web.properties_of(EventName.RATE_LIMIT_EXCEEDED)["scope"] == "session"


def test_a_429_still_carries_the_security_headers() -> None:
    """Limits run inside the headers middleware, so rejections are hardened too."""
    web = build_harness(rate_limit_config=RateLimitConfig(per_ip=1))
    web.client.get("/healthz")

    response = web.client.get("/healthz")

    assert response.status_code == 429
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Request-Id"]
