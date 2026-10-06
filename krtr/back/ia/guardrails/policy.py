"""Applies the G13 hard rules that can be decided without the LLM.

Exists so a conversation that keeps asking the same thing is closed deterministically. A
message counts as a repeat, anywhere in the recent window (not only back to back), when:
- its text is nearly the same as an earlier message (embedding similarity, before matching);
- or it resolves to the same request — same intent, same details — as an earlier one, however
  it is worded. Similarity alone cannot tell a rewording from the same question about another
  product (those score higher), so the request is what decides.

A message flagged aggressive or off-topic is closed only when the LLM confirms the flag
(`GuardConfirmer`); without an LLM, flags only flag. Consumed by `engine/engine.py`.
"""

import json
import logging
from typing import Protocol

import numpy as np

from krtr.back.ia.config import IaConfig
from krtr.back.ia.matching.artifacts import MatchKind, MatchResult
from krtr.back.ia.matching.labels import GuardLabel
from krtr.back.ia.matching.thresholds import LanguageThresholds
from krtr.back.ia.reasoning.artifacts import Closed, ClosureReason, ConversationState, Resolved
from krtr.back.ia.text import normalize_text
from krtr.back.security.oidc.artifacts import InterfaceLanguage

logger = logging.getLogger(__name__)

# The flags a confirmed "yes" closes on, with the reason each one closes with.
CLOSING_FLAGS: dict[GuardLabel, ClosureReason] = {
    GuardLabel.AGGRESSIVE: ClosureReason.AGGRESSIVE,
    GuardLabel.OFF_TOPIC: ClosureReason.OFF_TOPIC,
}


class GuardConfirmer(Protocol):
    """Confirms a guard flag. Implemented by `reasoning/llm/tasks.LlmTasks`."""

    def confirm_guard(self, label: GuardLabel, reply: str, language: InterfaceLanguage) -> bool:
        """Tells whether the flagged message really is what the label says.

        Args:
            label: The flag.
            reply: The customer's message.
            language: The customer's language.

        Returns:
            bool: True only on a clear "yes".
        """
        ...


class GuardrailPolicy:
    """The deterministic hard rules.

    Exists so the rules and their limits live in one tested unit. Built by `engine/factory.py`.
    """

    def __init__(
        self,
        config: IaConfig,
        thresholds: LanguageThresholds,
        confirmer: GuardConfirmer | None = None,
    ) -> None:
        """Keeps the limits and, if an LLM is selected, the confirmer of guard flags.

        Args:
            config: The conversation limits.
            thresholds: The selected model's thresholds per language (`repeat` is used).
            confirmer: Confirms a flag before closing; None to never close on a flag.
        """
        self._config = config
        self._thresholds = thresholds
        self._confirmer = confirmer

    def check(
        self,
        state: ConversationState,
        text: str,
        vector: np.ndarray,
        language: InterfaceLanguage,
    ) -> Closed | None:
        """Closes the conversation when the message repeats earlier ones too often.

        A bare option number ("1", "2") is never counted: it is how the customer answers
        questions, so it repeats legitimately.

        Args:
            state: The conversation, with the embeddings of its recent messages.
            text: The customer's message.
            vector: The message's L2-normalised embedding.
            language: The turn's language, whose `repeat` threshold applies.

        Returns:
            Closed | None: the closure, or None if no rule applies.
        """
        if normalize_text(text).isdigit() or not state.recent_embeddings:
            return None
        similarities = np.array(state.recent_embeddings, dtype=np.float32) @ vector
        repeats = int((similarities >= self._thresholds[language].repeat).sum()) + 1
        if repeats < self._config.repetition_limit:
            return None
        logger.info("Message repeated %d times in incident %s", repeats, state.incident_id)
        return Closed(reason=ClosureReason.REPETITIVE)

    def check_request(self, state: ConversationState, resolution: Resolved) -> Closed | None:
        """Closes the conversation when the same request was already resolved too often.

        Args:
            state: The conversation, with the requests resolved in the recent window.
            resolution: The complete request this turn resolved to.

        Returns:
            Closed | None: the closure, or None if no rule applies.
        """
        repeats = state.recent_requests.count(request_signature(resolution)) + 1
        if repeats < self._config.repetition_limit:
            return None
        logger.info("Request repeated %d times in incident %s", repeats, state.incident_id)
        return Closed(reason=ClosureReason.REPETITIVE)

    def check_flags(
        self, state: ConversationState, text: str, match: MatchResult, language: InterfaceLanguage
    ) -> Closed | None:
        """Closes on an aggressive or off-topic flag, only once the confirmer says yes (G13).

        A matched request is never closed: the customer gets their answer.

        Args:
            state: The conversation.
            text: The customer's message.
            match: The matcher's verdict, with its flags.
            language: The customer's language.

        Returns:
            Closed | None: the closure, or None if no flag is confirmed.
        """
        if self._confirmer is None or match.kind == MatchKind.MATCHED:
            return None
        for label in match.guard_flags:
            reason = CLOSING_FLAGS.get(label)
            if reason and self._confirmer.confirm_guard(label, text, language):
                logger.info("Confirmed %s in incident %s: closing", label, state.incident_id)
                return Closed(reason=reason)
        return None


def request_signature(resolution: Resolved) -> str:
    """Identifies a request by its intent and details, independent of the wording.

    Args:
        resolution: A complete request.

    Returns:
        str: e.g. '["account_balance", [["product_type", "savings_account"]]]'.
    """
    slots = sorted((str(name), value) for name, value in resolution.slots.items())
    return json.dumps([resolution.intent.value, slots])
