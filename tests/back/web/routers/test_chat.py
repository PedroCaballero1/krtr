"""Tests the chat routes (task 4.9): replies, case ownership, validation and the audit event.

Acceptance: a fake file type answers 415, an oversized note 413, and replies come in ES and PT.
"""

import httpx
import pytest

from krtr.back.security.audit.event_names import EventName
from krtr.back.web.chat.audio import MAX_AUDIO_BYTES
from krtr.back.web.chat.responder import PLACEHOLDER_REPLIES
from tests.back.web.fakes import WebHarness, build_harness

WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 100
MP4 = b"\x00\x00\x00\x20ftypM4A " + b"\x00" * 100
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100


@pytest.fixture
def web() -> WebHarness:
    """Builds the app (with the D15 placeholder responder) and logs a customer in."""
    harness = build_harness()
    harness.log_in()
    return harness


def open_case(web: WebHarness) -> str:
    """Opens a case for the logged-in customer and returns its ID."""
    return web.post("/api/cases").json()["incident_id"]


def send_text(
    web: WebHarness, incident_id: str, text: str = "hola", language: str = "es"
) -> httpx.Response:
    """Sends a text message the way the SPA does."""
    body = {"incident_id": incident_id, "text": text, "language": language}
    return web.post("/api/chat/messages", json=body)


def send_voice(
    web: WebHarness, incident_id: str, content: bytes, content_type: str, language: str = "es"
) -> httpx.Response:
    """Sends a voice note as multipart, the way the SPA does."""
    return web.post(
        "/api/chat/voice",
        data={"incident_id": incident_id, "language": language},
        files={"audio": ("note", content, content_type)},
    )


@pytest.mark.parametrize(("language", "lang_code"), [("es", "es"), ("pt-BR", "pt-BR")])
def test_a_message_gets_a_complete_reply_in_its_language(
    web: WebHarness, language: str, lang_code: str
) -> None:
    """One complete reply per message, in the interface's language (D15, G9, G14)."""
    incident_id = open_case(web)

    response = send_text(web, incident_id, language=language)

    assert response.status_code == 200
    body = response.json()
    assert body["incident_id"] == incident_id
    assert body["reply"] == PLACEHOLDER_REPLIES[lang_code]
    assert body["responded_at"]


def test_each_reply_is_audited_without_its_text(web: WebHarness) -> None:
    """chat_response_received carries the customer, case and latency, never what was said."""
    incident_id = open_case(web)

    send_text(web, incident_id, text="mi saldo secreto")

    audit = web.properties_of(EventName.CHAT_RESPONSE_RECEIVED)
    assert audit["incident_id"] == incident_id
    assert audit["customer_id"] == "12345678"
    assert audit["latency_ms"] >= 0
    assert "mi saldo secreto" not in str(audit)
    assert PLACEHOLDER_REPLIES["es"] not in str(audit)


def test_another_customers_case_gets_the_same_404_as_a_missing_one(web: WebHarness) -> None:
    """Chatting on B's case must look exactly like chatting on a case that does not exist."""
    web.log_in("B")
    b_case = open_case(web)
    web.log_in("A")

    foreign = send_text(web, b_case)
    missing = send_text(web, "INC-DOESNOTEXI")

    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json()


@pytest.mark.parametrize(
    "body",
    [
        {"text": "x" * 2001, "language": "es"},
        {"text": "   ", "language": "es"},
        {"text": "", "language": "es"},
        {"text": "hola", "language": "en"},
    ],
)
def test_a_message_outside_the_contract_is_422(web: WebHarness, body: dict) -> None:
    """2,000 characters at most, not blank, and only ES or PT (D6, G14)."""
    incident_id = open_case(web)

    response = web.post("/api/chat/messages", json={"incident_id": incident_id, **body})

    assert response.status_code == 422


def test_2000_characters_are_accepted(web: WebHarness) -> None:
    """The limit is inclusive."""
    assert send_text(web, open_case(web), text="x" * 2000).status_code == 200


@pytest.mark.parametrize(
    ("content", "content_type"), [(WEBM, "audio/webm;codecs=opus"), (MP4, "audio/mp4")]
)
def test_a_voice_note_gets_a_reply(web: WebHarness, content: bytes, content_type: str) -> None:
    """WebM/Opus (Chrome, Firefox) and MP4/AAC (Safari) both work (G8)."""
    response = send_voice(web, open_case(web), content, content_type, language="pt-BR")

    assert response.status_code == 200
    assert response.json()["reply"] == PLACEHOLDER_REPLIES["pt-BR"]


def test_a_fake_file_type_is_415(web: WebHarness) -> None:
    """An image sent as audio/webm is caught by its bytes."""
    response = send_voice(web, open_case(web), PNG, "audio/webm")

    assert response.status_code == 415
    assert response.json() == {
        "error": "unsupported_audio",
        "message_key": "chat_error_voice_unsupported",
    }


def test_a_note_over_2_mb_is_413(web: WebHarness) -> None:
    """D6: 2 MB at most."""
    response = send_voice(web, open_case(web), WEBM + b"\x00" * MAX_AUDIO_BYTES, "audio/webm")

    assert response.status_code == 413


def test_a_voice_note_on_another_customers_case_is_404(web: WebHarness) -> None:
    """The case is checked before the audio is even read."""
    response = send_voice(web, "INC-DOESNOTEXI", WEBM, "audio/webm")

    assert response.status_code == 404


@pytest.mark.parametrize("path", ["/api/chat/messages", "/api/chat/voice"])
def test_chat_routes_need_csrf(web: WebHarness, path: str) -> None:
    """A cross-site page must not be able to chat as the customer (task 4.5)."""
    response = web.client.post(
        path, json={"incident_id": "INC-X", "text": "hola", "language": "es"}
    )

    assert response.status_code == 403


def test_chat_routes_need_a_session() -> None:
    """Without a session there is no customer to answer for."""
    web = build_harness()

    response = web.client.post(
        "/api/chat/messages", json={"incident_id": "INC-X", "text": "hola", "language": "es"}
    )

    assert response.status_code == 401
