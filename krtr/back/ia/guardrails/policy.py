"""Applies the G13 hard rules that can be decided without a model.

Exists so a conversation that keeps repeating the same message is closed deterministically
before any matching happens. The guard labels (aggressive, off-topic) only flag in phase 1:
closing on them waits for the LLM's confirmation (phase 3). Consumed by `engine/engine.py`.
"""

import logging

from krtr.back.ia.config import IaConfig
from krtr.back.ia.reasoning.artifacts import Closed, ClosureReason, ConversationState
from krtr.back.ia.text import normalize_text

logger = logging.getLogger(__name__)


class GuardrailPolicy:
    """The deterministic hard rules.

    Exists so the rules and their limits live in one tested unit. Built by `engine/factory.py`.
    """

    def __init__(self, config: IaConfig) -> None:
        """Keeps the repetition limit.

        Args:
            config: The conversation limits.
        """
        self._config = config

    def check(self, state: ConversationState, text: str) -> Closed | None:
        """Closes the conversation when the message repeats an earlier one too often.

        A bare option number ("1", "2") is never counted: it is how the customer answers
        questions, so it repeats legitimately.

        Args:
            state: The conversation, with its recent messages already normalised.
            text: The customer's message.

        Returns:
            Closed | None: the closure, or None if no rule applies.
        """
        normalized = normalize_text(text)
        if normalized.isdigit():
            return None
        repeats = state.recent_messages.count(normalized) + 1
        if repeats < self._config.repetition_limit:
            return None
        logger.info("Message repeated %d times in incident %s", repeats, state.incident_id)
        return Closed(reason=ClosureReason.REPETITIVE)
