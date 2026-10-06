"""Defines the chat routes: POST /api/chat/messages and POST /api/chat/voice (task 4.9, §3.4).

Exists so the chat screen gets one complete reply per message (no streaming, G9). Before any
reply, the case must be one of the session customer's (otherwise the same 404 as the case
routes), and the request must pass CSRF. Each reply is recorded as `chat_response_received`
with the responder's metadata and the server-side latency, never the text (G21). Consumed by
`krtr/back/web/app.py`.
"""

import logging
import time
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from krtr.back.security.audit.event_names import EventName
from krtr.back.security.clock import utc_now
from krtr.back.security.oidc.artifacts import InterfaceLanguage
from krtr.back.security.sessions.artifacts import SessionRecord
from krtr.back.web.auditing import schedule_event
from krtr.back.web.cases.artifacts import INCIDENT_ID_MAX_LENGTH
from krtr.back.web.cases.repository import CaseRepository
from krtr.back.web.chat.artifacts import ChatAnswer, ChatMessageRequest, ChatReply
from krtr.back.web.chat.audio import AudioRejection, InvalidAudio, read_voice_note
from krtr.back.web.chat.responder import ChatResponder
from krtr.back.web.csrf import require_session_with_csrf
from krtr.back.web.errors import ApiErrorCode, MessageKey, api_error
from krtr.back.web.routers.cases import case_not_found, get_case_repository

logger = logging.getLogger(__name__)

chat_router = APIRouter(prefix="/api/chat")

VoiceIncidentId = Annotated[str, Form(min_length=1, max_length=INCIDENT_ID_MAX_LENGTH)]


def get_chat_responder(request: Request) -> ChatResponder:
    """Returns the app's chat responder.

    Args:
        request: The current request, to reach the app's state.

    Returns:
        ChatResponder: the responder `create_app` was built with.
    """
    return request.app.state.chat_responder


@chat_router.post("/messages", response_model=ChatReply)
def send_message(
    payload: ChatMessageRequest,
    request: Request,
    tasks: BackgroundTasks,
    session: SessionRecord = Depends(require_session_with_csrf),
    cases: CaseRepository = Depends(get_case_repository),
    responder: ChatResponder = Depends(get_chat_responder),
) -> ChatReply | JSONResponse:
    """Answers a typed message for one of the customer's cases.

    Args:
        payload: The case, the text (1–2,000 characters) and the interface's language.
        request: The current request.
        tasks: Where the event is queued.
        session: The request's live session, past the CSRF checks.
        cases: The case repository, to check the case is the customer's.
        responder: Who answers.

    Returns:
        ChatReply | JSONResponse: the reply, or 404 when the case is not the customer's.
    """
    if cases.find_for_customer(session.customer_id, payload.incident_id) is None:
        return case_not_found()
    started = time.perf_counter()
    answer = responder.answer_text(
        session.customer_id, payload.incident_id, payload.text, payload.language
    )
    return _reply(request, tasks, session, payload.incident_id, answer, started)


@chat_router.post("/voice", response_model=ChatReply)
async def send_voice_note(
    request: Request,
    tasks: BackgroundTasks,
    incident_id: VoiceIncidentId,
    language: Annotated[InterfaceLanguage, Form()],
    audio: Annotated[UploadFile, File()],
    session: SessionRecord = Depends(require_session_with_csrf),
    cases: CaseRepository = Depends(get_case_repository),
    responder: ChatResponder = Depends(get_chat_responder),
) -> ChatReply | JSONResponse:
    """Answers a voice note (WebM/Opus or MP4/AAC, at most 2 MB) for one of the customer's cases.

    Args:
        request: The current request.
        tasks: Where the event is queued.
        incident_id: The case.
        language: The interface's language.
        audio: The recorded note; validated, then discarded.
        session: The request's live session, past the CSRF checks.
        cases: The case repository, to check the case is the customer's.
        responder: Who answers.

    Returns:
        ChatReply | JSONResponse: the reply; 404 when the case is not the customer's, 413 when
        the note is over 2 MB, 415 when it is not WebM or MP4 audio.
    """
    if cases.find_for_customer(session.customer_id, incident_id) is None:
        return case_not_found()
    try:
        await read_voice_note(audio)
    except InvalidAudio as rejection:
        return _reject_audio(rejection.reason)
    started = time.perf_counter()
    answer = await run_in_threadpool(
        responder.answer_voice, session.customer_id, incident_id, language
    )
    return _reply(request, tasks, session, incident_id, answer, started)


def _reply(
    request: Request,
    tasks: BackgroundTasks,
    session: SessionRecord,
    incident_id: str,
    answer: ChatAnswer,
    started: float,
) -> ChatReply:
    """Records the turn's metadata and builds the reply.

    Args:
        request: The current request.
        tasks: Where the event is queued.
        session: The customer's session.
        incident_id: The case.
        answer: What the responder said.
        started: `time.perf_counter()` when the responder was called.

    Returns:
        ChatReply: the reply, stamped with the current time.
    """
    properties: dict[str, Any] = {
        **answer.audit,
        "customer_id": session.customer_id,
        "incident_id": incident_id,
        "latency_ms": round((time.perf_counter() - started) * 1000, 1),
    }
    schedule_event(request, tasks, EventName.CHAT_RESPONSE_RECEIVED, properties)
    return ChatReply(incident_id=incident_id, reply=answer.reply, responded_at=utc_now())


def _reject_audio(reason: AudioRejection) -> JSONResponse:
    """Answers a rejected voice note: 413 when too large, 415 otherwise.

    Args:
        reason: Why the note was rejected.

    Returns:
        JSONResponse: the error with the §3.4 body.
    """
    logger.warning("Rejected a voice note: %s", reason.value)
    if reason == AudioRejection.TOO_LARGE:
        return api_error(413, ApiErrorCode.AUDIO_TOO_LARGE, MessageKey.AUDIO_TOO_LARGE)
    return api_error(415, ApiErrorCode.UNSUPPORTED_AUDIO, MessageKey.UNSUPPORTED_AUDIO)
