"""Tests that every language detector of the Enum can be built."""

from krtr.back.ia.language.factory import build_language_detector
from krtr.back.ia.language.models import LanguageDetectorModel
from krtr.back.security.oidc.artifacts import InterfaceLanguage


def test_every_detector_of_the_enum_builds_and_detects() -> None:
    """Each member maps to a working detector."""
    for model in LanguageDetectorModel:
        guess = build_language_detector(model).detect("Quero saber o status da minha reclamação")

        assert guess is not None
        assert guess.language == InterfaceLanguage.PORTUGUESE
