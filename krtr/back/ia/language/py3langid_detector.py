"""Guesses ES or PT offline with py3langid, a small n-gram language identifier.

Exists as the default `LanguageDetector`: a 4 MB package on numpy (already a dependency),
deterministic, no network. Chosen over lingua (a 170 MB wheel) after both were tried on the
same ES / PT phrases; py3langid was the more confident on full sentences. Built by
`engine/factory.py`.
"""

from py3langid.langid import MODEL_FILE, LanguageIdentifier

from krtr.back.ia.language.artifacts import LanguageGuess
from krtr.back.ia.language.base import LanguageDetector
from krtr.back.security.oidc.artifacts import InterfaceLanguage

# py3langid's ISO 639-1 code for each supported language.
LANGUAGE_CODES: dict[InterfaceLanguage, str] = {
    InterfaceLanguage.SPANISH: "es",
    InterfaceLanguage.PORTUGUESE: "pt",
}


class Py3LangidLanguageDetector(LanguageDetector):
    """Classifies a text as ES or PT, with probabilities normalised over the two.

    Exists so the detector only ever chooses between the languages krtr supports.
    """

    def __init__(self) -> None:
        """Loads the bundled model, restricted to the supported languages."""
        self._identifier = LanguageIdentifier.from_model_file(MODEL_FILE, norm_probs=True)
        self._identifier.set_languages(list(LANGUAGE_CODES.values()))
        self._languages = {code: language for language, code in LANGUAGE_CODES.items()}

    def detect(self, text: str) -> LanguageGuess | None:
        """Guesses the text's language.

        Args:
            text: The customer's message.

        Returns:
            LanguageGuess | None: the likelier language and its probability, or None for text
            without letters (an option number or an ID gives no clue).
        """
        if not any(character.isalpha() for character in text):
            return None
        code, probability = self._identifier.classify(text)
        return LanguageGuess(language=self._languages[code], confidence=float(probability))
