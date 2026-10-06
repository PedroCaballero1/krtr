"""Defines the contracts shared across the `krtr/back/ia/` vertical.

Exists to keep what goes into a turn (`UserTurn`), what comes out (`AgentReply`) and what the
writer phrases (`ReplyContent`) in one discoverable place. It depends only on leaf modules (the
intent and match enums), so `deterministic/`, `reasoning/`, `writing/` and `engine/` can all
import it without cycles.
"""

from enum import StrEnum

from pydantic import BaseModel, Field

from krtr.back.ia.deterministic.intents import Intent
from krtr.back.ia.matching.artifacts import MatchKind
from krtr.back.ia.matching.labels import GuardLabel
from krtr.back.security.oidc.artifacts import InterfaceLanguage


class TurnOutcome(StrEnum):
    """How a turn ended, for the caller and for the event log.

    Exists so the web layer and the CLI can tell an answered question from a clarification
    request or a terminal outcome without parsing the reply text. Consumed by `engine/` and
    `reasoning/`.
    """

    RESOLVED = "resolved"  # A deterministic action answered.
    NEEDS_CLARIFICATION = "needs_clarification"
    ESCALATED = "escalated"  # Handed to a human (G20); the conversation ends.
    CLOSED = "closed"  # Closed by a hard rule (G13); the conversation ends.


class MessageKey(StrEnum):
    """Every message the agent can say, keyed into the ES / PT template catalogs.

    Exists because replies are phrased from templates, never from free text, so a reply can
    only state facts an action produced (docs/ia-proposal.md §1.1). Consumed by the actions,
    the clarifier, the engine and `writing/templates/`.
    """

    ACCOUNT_BALANCE = "account_balance"
    CREDIT_BALANCE = "credit_balance"  # A balance with its credit limit (cards, loans).
    NO_PRODUCTS = "no_products"  # The customer holds no product of the requested type.
    COMPLAINT_STATUS = "complaint_status"
    COMPLAINT_NOT_FOUND = "complaint_not_found"  # Also used for another customer's complaint.
    ASK_CHOOSE_INTENT = "ask_choose_intent"
    ASK_CHOOSE_OPTION = "ask_choose_option"
    ASK_PROVIDE_SLOT = "ask_provide_slot"
    ASK_REPHRASE = "ask_rephrase"
    ESCALATED = "escalated"
    CLOSED_REPETITIVE = "closed_repetitive"
    CLOSED_AGGRESSIVE = "closed_aggressive"
    CLOSED_OFF_TOPIC = "closed_off_topic"
    ESCALATED_UNSUPPORTED = "escalated_unsupported"  # Handed over without asking first.
    CONVERSATION_ENDED = "conversation_ended"  # A message after an escalation or a closure.


class CustomerContext(BaseModel):
    """Who the customer is, taken from the session and never from a model's output.

    Exists as the only way an action learns whose data it may read, so no text the customer
    types can make it read someone else's (G13). Built by `engine/` from `UserTurn`.
    """

    customer_id: str


class ReplyContent(BaseModel):
    """What a reply says, before it is phrased: a message key and the values it may show.

    Exists so actions, the clarifier and the engine produce facts while `writing/` alone
    decides the wording in each language. `items` holds repeated lines, such as one balance
    per product or one option per candidate.
    """

    message_key: MessageKey
    values: dict[str, str] = Field(default_factory=dict)
    items: list[dict[str, str]] = Field(default_factory=list)


class UserTurn(BaseModel):
    """One customer message for a case, as the web layer or the CLI hands it to the engine.

    Exists so the engine's input carries the session's customer next to the text, and the
    engine never has to trust an identifier inside the text.
    """

    incident_id: str
    customer_id: str
    text: str = Field(min_length=1)
    language: InterfaceLanguage = InterfaceLanguage.SPANISH  # A hint: the interface's language.


class TurnStep(StrEnum):
    """The steps of a turn whose duration is measured (G16).

    Exists so every response's latency can be broken down the same way in the log, the CLI and
    the `chat_response_received` event. Consumed by `timing.py` and `engine/engine.py`.
    """

    LANGUAGE = "language"
    GUARDRAILS = "guardrails"
    EMBEDDING = "embedding"
    MATCHING = "matching"
    RESOLUTION = "resolution"
    ACTION = "action"  # Running the action, or recording the question or the ending.
    WRITING = "writing"
    PERSISTENCE = "persistence"  # Saving the conversation's state, the message and the reply.
    LLM = "llm"  # Time inside LLM calls, already counted in the step that made them.


class TurnTimings(BaseModel):
    """How long a turn took, in total and per step, in milliseconds.

    Exists so each response carries its own latency. A step that did not run (e.g. matching on
    a closed conversation) is absent; the total also covers loading and saving state.
    """

    total_ms: float = Field(ge=0)
    steps_ms: dict[TurnStep, float] = Field(default_factory=dict)


class TurnDetails(BaseModel):
    """What the agent understood in a turn: the metadata recorded in `events` (G21).

    Exists so the web chat endpoint can record each response's `chat_response_received`
    event without the reply text, which belongs in the messages table instead. Every field
    is empty when the turn never reached matching (a closed or ended conversation).
    """

    intent: Intent | None = None  # Resolved, or being asked about.
    match_kind: MatchKind | None = None
    guard_flags: list[GuardLabel] = Field(default_factory=list)
    llm_used: bool = False  # Whether the LLM was called during the turn.


class AgentReply(BaseModel):
    """The engine's answer to one turn.

    Exists as the return contract of `ConversationEngine.handle`, consumed by the web chat
    endpoint and by `krtr back ia`.
    """

    incident_id: str
    reply: str
    language: InterfaceLanguage  # The language the reply is written in.
    outcome: TurnOutcome
    timings: TurnTimings
    details: TurnDetails = Field(default_factory=TurnDetails)
