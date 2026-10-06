"""Defines how krtr-web gets a reply for a chat message (task 4.9, G7, G9).

Exists so the chat routes only know `ChatResponder`, and whoever produces the reply (the
placeholder of D15, or the conversation engine of `krtr/back/ia/`) can change without touching
them. `StubChatResponder` answers the D15 placeholder; `AgentChatResponder`
(`krtr/back/web/chat/agent.py`) answers with the engine. Consumed by `krtr/back/web/app.py` and
`krtr/back/web/routers/chat.py`.
"""

from enum import StrEnum
from typing import Protocol

from krtr.back.security.oidc.artifacts import InterfaceLanguage
from krtr.back.web.chat.artifacts import ChatAnswer


class ResponderName(StrEnum):
    """Which responder answered a turn, recorded in `chat_response_received`."""

    STUB = "stub"  # The D15 placeholder.
    AGENT = "agent"  # The conversation engine of krtr/back/ia/.


class MessageKind(StrEnum):
    """What the customer sent: typed text or a voice note."""

    TEXT = "text"
    VOICE = "voice"


# D15: the placeholder until the assistant answers, in each interface language.
PLACEHOLDER_REPLIES: dict[InterfaceLanguage, str] = {
    InterfaceLanguage.SPANISH: (
        "Gracias por tu mensaje. Nuestro asistente estará disponible muy pronto."
    ),
    InterfaceLanguage.PORTUGUESE: (
        "Obrigado pela sua mensagem. Nosso assistente estará disponível em breve."
    ),
}


class ChatResponder(Protocol):
    """Answers a customer's chat messages. Consumed by `krtr/back/web/routers/chat.py`."""

    def answer_text(
        self, customer_id: str, incident_id: str, text: str, language: InterfaceLanguage
    ) -> ChatAnswer:
        """Answers a typed message.

        Args:
            customer_id: The customer, from the session.
            incident_id: The case, already checked to be the customer's.
            text: The message, 1–2,000 characters.
            language: The interface's language.

        Returns:
            ChatAnswer: the reply and the turn's metadata.
        """
        ...

    def answer_voice(
        self, customer_id: str, incident_id: str, language: InterfaceLanguage
    ) -> ChatAnswer:
        """Answers a voice note, already validated (format, size); its audio is not kept.

        Args:
            customer_id: The customer, from the session.
            incident_id: The case, already checked to be the customer's.
            language: The interface's language.

        Returns:
            ChatAnswer: the reply and the turn's metadata.
        """
        ...


class StubChatResponder:
    """Answers every message with the D15 placeholder in the interface's language.

    Exists so the chat works end to end before (or without) the conversation engine, and as the
    voice answer while speech-to-text is out of scope (G8, G10).
    """

    def answer_text(
        self, customer_id: str, incident_id: str, text: str, language: InterfaceLanguage
    ) -> ChatAnswer:
        """Answers a typed message with the placeholder.

        Args:
            customer_id: The customer (unused by the placeholder beyond the protocol).
            incident_id: The case.
            text: The message.
            language: The interface's language.

        Returns:
            ChatAnswer: the placeholder and the turn's metadata.
        """
        return placeholder_answer(language, MessageKind.TEXT)

    def answer_voice(
        self, customer_id: str, incident_id: str, language: InterfaceLanguage
    ) -> ChatAnswer:
        """Answers a voice note with the placeholder.

        Args:
            customer_id: The customer.
            incident_id: The case.
            language: The interface's language.

        Returns:
            ChatAnswer: the placeholder and the turn's metadata.
        """
        return placeholder_answer(language, MessageKind.VOICE)


def placeholder_answer(language: InterfaceLanguage, kind: MessageKind) -> ChatAnswer:
    """Builds the D15 placeholder answer for one message.

    Exists so the stub and the agent's voice path answer identically.

    Args:
        language: The interface's language.
        kind: Whether the customer typed or spoke.

    Returns:
        ChatAnswer: the placeholder, with the responder, kind and language as metadata.
    """
    return ChatAnswer(
        reply=PLACEHOLDER_REPLIES[language],
        audit={
            "responder": ResponderName.STUB.value,
            "kind": kind.value,
            "language": language.value,
        },
    )
