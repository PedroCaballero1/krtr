"""Defines the contracts of krtr-web's chat endpoints (task 4.9, §3.4).

Exists so the text message, the reply, and what a responder hands back to the route have one
typed shape each. Consumed by `krtr/back/web/chat/` and `krtr/back/web/routers/chat.py`.
"""

from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, Field, StringConstraints

from krtr.back.security.oidc.artifacts import InterfaceLanguage
from krtr.back.web.cases.artifacts import INCIDENT_ID_MAX_LENGTH

MAX_MESSAGE_LENGTH = 2000  # D6.

IncidentId = Annotated[str, StringConstraints(min_length=1, max_length=INCIDENT_ID_MAX_LENGTH)]
MessageText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_MESSAGE_LENGTH)
]


class ChatMessageRequest(BaseModel):
    """The `POST /api/chat/messages` body: a 1–2,000 character text for one case."""

    incident_id: IncidentId
    text: MessageText
    language: InterfaceLanguage


class ChatReply(BaseModel):
    """What both chat endpoints answer: the reply and when it was given (§3.4)."""

    incident_id: str
    reply: str
    responded_at: datetime


class ChatAnswer(BaseModel):
    """What a responder hands back to the route.

    Exists so the route gets the reply text to send and, apart from it, the turn's metadata to
    record as `chat_response_received` (G21). `audit` never holds the text: replies carry
    balances and card numbers, which belong in the `messages` table only.
    """

    reply: str
    audit: dict[str, Any] = Field(default_factory=dict)
