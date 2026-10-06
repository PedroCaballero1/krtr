"""Tests StubChatResponder: the D15 placeholder in the interface's language."""

import pytest

from krtr.back.security.oidc.artifacts import InterfaceLanguage
from krtr.back.web.chat.responder import StubChatResponder


@pytest.mark.parametrize(
    ("language", "reply"),
    [
        (
            InterfaceLanguage.SPANISH,
            "Gracias por tu mensaje. Nuestro asistente estará disponible muy pronto.",
        ),
        (
            InterfaceLanguage.PORTUGUESE,
            "Obrigado pela sua mensagem. Nosso assistente estará disponível em breve.",
        ),
    ],
)
def test_text_and_voice_get_the_d15_placeholder(language: InterfaceLanguage, reply: str) -> None:
    """D15 fixes the exact wording in ES and PT."""
    stub = StubChatResponder()

    text = stub.answer_text("C1", "INC-1", "hola", language)
    voice = stub.answer_voice("C1", "INC-1", language)

    assert text.reply == voice.reply == reply
    assert (text.audit["kind"], voice.audit["kind"]) == ("text", "voice")
    assert text.audit["language"] == language.value
