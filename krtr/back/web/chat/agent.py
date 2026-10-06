"""Answers chat messages with the conversation engine of `krtr/back/ia/` (task 4.9).

Exists as the bridge `docs/ia-proposal.md` §4 describes: the web layer only knows
`ChatResponder`, and this class turns each message into a `UserTurn`, runs the engine, and hands
back the reply plus the turn's metadata (outcome, intent, match kind, guard flags, language and
latency per step) for `chat_response_received`, never the text. Voice notes get the D15
placeholder while speech-to-text is out of scope. Consumed by `krtr/back/web/app.py`.
"""

import logging
from typing import Any

from krtr.back.ia.artifacts import AgentReply, UserTurn
from krtr.back.ia.config import IaModelsConfig
from krtr.back.ia.deterministic.config import DeterministicConfig
from krtr.back.ia.deterministic.neon_readers import NeonComplaintsReader, NeonProductsReader
from krtr.back.ia.engine.config import EngineConfig
from krtr.back.ia.engine.engine import ConversationEngine
from krtr.back.ia.engine.factory import build_engine
from krtr.back.ia.engine.store import InMemoryConversationStateStore
from krtr.back.ia.messages.store import MessageStore
from krtr.back.security.oidc.artifacts import InterfaceLanguage
from krtr.back.web.chat.artifacts import ChatAnswer
from krtr.back.web.chat.responder import (
    MessageKind,
    ResponderName,
    placeholder_answer,
)
from krtr.database.neon.client import NeonClient

logger = logging.getLogger(__name__)

# The complaint IDs of the `complaints` table, e.g. CMP-J7LT0TPC5YC33ULTQJZD (Q-A of
# tasks/todo.md), typed in any case: the extractor upper-cases what it finds.
COMPLAINT_ID_PATTERN = r"(?i)\bCMP-[A-Z0-9]{20}\b"


class AgentChatResponder:
    """Answers typed messages with the conversation engine.

    Exists as the production `ChatResponder`. Consumed by `krtr/back/web/routers/chat.py`.
    """

    def __init__(self, engine: ConversationEngine) -> None:
        """Builds the responder on a ready engine.

        Args:
            engine: The conversation engine, with its readers, state and message stores.
        """
        self._engine = engine

    def answer_text(
        self, customer_id: str, incident_id: str, text: str, language: InterfaceLanguage
    ) -> ChatAnswer:
        """Answers a typed message with the engine.

        Args:
            customer_id: The customer, from the session.
            incident_id: The case, already checked to be the customer's.
            text: The message.
            language: The interface's language, the engine's starting hint (G14).

        Returns:
            ChatAnswer: the engine's reply and the turn's metadata.
        """
        turn = UserTurn(
            incident_id=incident_id, customer_id=customer_id, text=text, language=language
        )
        reply = self._engine.handle(turn)
        return ChatAnswer(reply=reply.reply, audit=turn_audit(reply))

    def answer_voice(
        self, customer_id: str, incident_id: str, language: InterfaceLanguage
    ) -> ChatAnswer:
        """Answers a voice note with the D15 placeholder; the engine only reads text.

        Args:
            customer_id: The customer.
            incident_id: The case.
            language: The interface's language.

        Returns:
            ChatAnswer: the placeholder and the turn's metadata.
        """
        return placeholder_answer(language, MessageKind.VOICE)


def turn_audit(reply: AgentReply) -> dict[str, Any]:
    """Builds the `chat_response_received` properties of one engine turn, without its text.

    Args:
        reply: The engine's answer.

    Returns:
        dict[str, Any]: responder, kind, outcome, language, intent, match kind, guard flags and
        the latency in total and per step, in milliseconds.
    """
    details = reply.details
    return {
        "responder": ResponderName.AGENT.value,
        "kind": MessageKind.TEXT.value,
        "outcome": reply.outcome.value,
        "language": reply.language.value,
        "intent": details.intent.value if details.intent else None,
        "match_kind": details.match_kind.value if details.match_kind else None,
        "guard_flags": [flag.value for flag in details.guard_flags],
        "total_ms": round(reply.timings.total_ms, 1),
        "steps_ms": {step.value: round(ms, 1) for step, ms in reply.timings.steps_ms.items()},
    }


def build_agent_responder(client: NeonClient, messages: MessageStore) -> AgentChatResponder:
    """Builds the engine over Neon's products and complaints and wraps it as a responder.

    The models (embedding, language detector, LLM) come from `IaModelsConfig.resolve()`: the
    KRTR_IA_* variables of the container, else the vertical's defaults. The conversation state
    lives in memory (krtr-web runs one container, D8), while each message and reply goes to
    `messages`.

    Args:
        client: The pooled Neon client the readers query.
        messages: Where each message and reply is stored.

    Returns:
        AgentChatResponder: the ready responder.

    Raises:
        ValueError: if a model name is unknown, or the engine's catalog, templates or
            thresholds are incomplete.
    """
    config = EngineConfig(
        deterministic=DeterministicConfig(complaint_id_pattern=COMPLAINT_ID_PATTERN),
        models=IaModelsConfig.resolve(),
    )
    logger.info(
        "Chat models: embedding %s, language %s, LLM %s",
        config.models.embedding.value,
        config.models.language.value,
        config.models.llm.value,
    )
    engine = build_engine(
        products=NeonProductsReader(client),
        complaints=NeonComplaintsReader(client),
        store=InMemoryConversationStateStore(),
        messages=messages,
        config=config,
    )
    logger.info("The chat answers with the conversation engine")
    return AgentChatResponder(engine)
