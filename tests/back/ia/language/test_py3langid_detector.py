"""Tests the offline detector on real ES and PT phrases from the catalog's domain."""

import pytest

from krtr.back.ia.language.config import LanguageConfig
from krtr.back.ia.language.py3langid_detector import Py3LangidLanguageDetector
from krtr.back.security.oidc.artifacts import InterfaceLanguage

DETECTOR = Py3LangidLanguageDetector()
MIN_CONFIDENCE = LanguageConfig().min_confidence


@pytest.mark.parametrize(
    ("text", "language"),
    [
        ("Necesito consultar el saldo de mi tarjeta de crédito", InterfaceLanguage.SPANISH),
        ("Quiero saber el estado de mi queja", InterfaceLanguage.SPANISH),
        ("¿Cuál es mi saldo?", InterfaceLanguage.SPANISH),
        ("Preciso consultar o saldo do meu cartão de crédito", InterfaceLanguage.PORTUGUESE),
        ("Quero saber o status da minha reclamação", InterfaceLanguage.PORTUGUESE),
        ("Qual é o meu saldo?", InterfaceLanguage.PORTUGUESE),
    ],
)
def test_full_sentences_pass_the_default_confidence_gate(
    text: str, language: InterfaceLanguage
) -> None:
    """The kind of sentence that should set a conversation's language does."""
    guess = DETECTOR.detect(text)

    assert guess is not None
    assert guess.language == language
    assert guess.confidence >= MIN_CONFIDENCE


@pytest.mark.parametrize("text", ["1", "104233", "  ?!  "])
def test_text_without_letters_gives_no_guess(text: str) -> None:
    """Option numbers carry no language at all."""
    assert DETECTOR.detect(text) is None
