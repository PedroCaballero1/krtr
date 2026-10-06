"""Defines the state of a conversation and how a turn is resolved.

Exists to keep the resolver's contracts — the question waiting for an answer, the
conversation's memory, and the four possible resolutions — in one place shared by the
resolver, the clarifier, the guardrails and the engine.
"""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from krtr.back.ia.artifacts import TurnOutcome
from krtr.back.ia.deterministic.intents import Intent
from krtr.back.security.oidc.artifacts import InterfaceLanguage


class QuestionKind(StrEnum):
    """What the agent asked the customer, so their reply can be read against it."""

    CHOOSE_INTENT = "choose_intent"  # Pick one of several plausible intents.
    CHOOSE_OPTION = "choose_option"  # Pick one value of a closed slot (e.g. product type).
    PROVIDE_SLOT = "provide_slot"  # Type a free value (e.g. a complaint ID).
    REPHRASE = "rephrase"  # Nothing matched: say it another way.


class EscalationReason(StrEnum):
    """Why a conversation is handed to a human (G20)."""

    CLARIFICATION_LIMIT = "clarification_limit"


class ClosureReason(StrEnum):
    """Why a hard rule closed a conversation (G13)."""

    REPETITIVE = "repetitive"


class PendingQuestion(BaseModel):
    """The question the customer's next message is expected to answer.

    Exists so a reply such as "2" or "the card" is read against what was asked. `intent` and
    `collected` carry the slot filling in progress; `options` holds intent or slot values.
    """

    kind: QuestionKind
    intent: Intent | None = None
    slot: str | None = None
    options: list[str] = Field(default_factory=list)
    collected: dict[str, str] = Field(default_factory=dict)


class ConversationState(BaseModel):
    """What the agent remembers about one case between turns.

    Exists so the clarification flow and the hard rules can span several messages. Kept by a
    `ConversationStateStore`, keyed by customer and incident.
    """

    incident_id: str
    customer_id: str
    pending: PendingQuestion | None = None
    clarification_attempts: int = 0
    recent_messages: list[str] = Field(default_factory=list)  # Normalised, newest last.
    ended: TurnOutcome | None = None  # Set once the case is escalated or closed.
    language: InterfaceLanguage | None = None  # Set by the first clear message (G14).


class Resolved(BaseModel):
    """The intent is known, with the slots gathered so far (the resolver checks the rest)."""

    kind: Literal[TurnOutcome.RESOLVED] = TurnOutcome.RESOLVED
    intent: Intent
    slots: dict[str, str] = Field(default_factory=dict)


class NeedsClarification(BaseModel):
    """The customer must answer a question first."""

    kind: Literal[TurnOutcome.NEEDS_CLARIFICATION] = TurnOutcome.NEEDS_CLARIFICATION
    question: PendingQuestion


class Escalated(BaseModel):
    """The case goes to a human."""

    kind: Literal[TurnOutcome.ESCALATED] = TurnOutcome.ESCALATED
    reason: EscalationReason


class Closed(BaseModel):
    """A hard rule ended the conversation."""

    kind: Literal[TurnOutcome.CLOSED] = TurnOutcome.CLOSED
    reason: ClosureReason


Resolution = Annotated[
    Resolved | NeedsClarification | Escalated | Closed, Field(discriminator="kind")
]
