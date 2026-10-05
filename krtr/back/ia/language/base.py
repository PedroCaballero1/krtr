"""Defines the contract of the components that guess the language a message is written in.

Exists so the conversation's language policy depends on "something that guesses ES or PT",
and the offline detector, a future model and test fakes can replace each other. Consumed by
`language/policy.py`.
"""

from abc import ABC, abstractmethod

from krtr.back.ia.language.artifacts import LanguageGuess


class LanguageDetector(ABC):
    """Guesses which supported language a text is written in."""

    @abstractmethod
    def detect(self, text: str) -> LanguageGuess | None:
        """Guesses the text's language among the supported ones.

        Args:
            text: The customer's message.

        Returns:
            LanguageGuess | None: the likeliest language and its confidence, or None if the
            text gives no clue at all.
        """
