"""Decides which language a conversation is replied in (G14).

Exists so the reply language follows what the customer writes instead of only the interface
selector, without flipping on the short replies the clarification flow is made of. The
caller's language is the starting hint; a clear message sets the conversation's language,
and a later clear message in the other language switches it. Consumed by `engine/engine.py`.
"""

import logging

from krtr.back.ia.language.base import LanguageDetector
from krtr.back.ia.language.config import LanguageConfig
from krtr.back.ia.reasoning.artifacts import ConversationState
from krtr.back.ia.text import normalize_text
from krtr.back.security.oidc.artifacts import InterfaceLanguage

logger = logging.getLogger(__name__)


class ConversationLanguagePolicy:
    """Keeps each conversation's language, updating it only on clear evidence.

    Exists so the detector's noise on short text never reaches the customer. Built by
    `engine/factory.py`.
    """

    def __init__(self, detector: LanguageDetector, config: LanguageConfig) -> None:
        """Keeps the detector and the gates a message must pass.

        Args:
            detector: Guesses a message's language.
            config: The minimum words and confidence.
        """
        self._detector = detector
        self._config = config

    def resolve(
        self, state: ConversationState, text: str, hint: InterfaceLanguage
    ) -> InterfaceLanguage:
        """Updates the conversation's language from the message, if clear, and returns it.

        Args:
            state: The conversation, whose `language` is updated in place.
            text: The customer's message.
            hint: The caller's language, used until a message sets one.

        Returns:
            InterfaceLanguage: the language to reply in.
        """
        detected = self._clear_language(text)
        if detected is not None and detected != state.language:
            logger.info("Conversation %s now in %s", state.incident_id, detected.value)
            state.language = detected
        return state.language or hint

    def _clear_language(self, text: str) -> InterfaceLanguage | None:
        """Returns the message's language only if it is long and the guess is confident.

        Args:
            text: The customer's message.

        Returns:
            InterfaceLanguage | None: the language, or None if the message is not clear enough.
        """
        if len(normalize_text(text).split()) < self._config.min_words:
            return None
        guess = self._detector.detect(text)
        if guess is None or guess.confidence < self._config.min_confidence:
            return None
        return guess.language
