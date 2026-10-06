"""Defines one stored chat message, as the `messages` table keeps it (G17).

Exists so the engine, the stores and the tests share one typed shape for a message or reply,
with the text in clear: only the Neon store encrypts it, at the database boundary.
"""

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from krtr.back.ia.artifacts import TurnOutcome
from krtr.back.security.oidc.artifacts import InterfaceLanguage


class MessageSender(StrEnum):
    """Who wrote a message, as `messages.sender` stores it."""

    CUSTOMER = "customer"
    AGENT = "agent"


class ConversationMessage(BaseModel):
    """One message of a case: the customer's text or the agent's reply.

    Exists as the row contract of `messages`. `outcome` is set on agent replies only.
    """

    message_id: UUID = Field(default_factory=uuid4)
    incident_id: str
    customer_id: str
    sender: MessageSender
    content: str
    language: InterfaceLanguage
    outcome: TurnOutcome | None = None
    sent_at: datetime
