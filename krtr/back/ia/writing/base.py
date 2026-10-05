"""Defines the contract of the components that phrase a reply.

Exists so the engine hands facts (`ReplyContent`) to "something that phrases them", and the
template writer of phase 1 and an optional LLM writer (phase 5) can replace each other.
Consumed by `engine/engine.py`.
"""

from abc import ABC, abstractmethod

from krtr.back.ia.artifacts import ReplyContent
from krtr.back.security.oidc.artifacts import InterfaceLanguage


class ResponseWriter(ABC):
    """Turns a reply's facts into text in the customer's language (G14)."""

    @abstractmethod
    def write(self, content: ReplyContent, language: InterfaceLanguage) -> str:
        """Phrases a reply.

        Args:
            content: The message key and the facts it may show.
            language: The customer's language.

        Returns:
            str: the reply text.
        """
