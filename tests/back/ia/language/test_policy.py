"""Tests when a message may set or switch a conversation's language, with a fake detector."""

from krtr.back.ia.language.artifacts import LanguageGuess
from krtr.back.ia.language.base import LanguageDetector
from krtr.back.ia.language.config import LanguageConfig
from krtr.back.ia.language.policy import ConversationLanguagePolicy
from krtr.back.ia.reasoning.artifacts import ConversationState
from krtr.back.security.oidc.artifacts import InterfaceLanguage
from tests.back.ia.fakes import CUSTOMER_ID

SPANISH = InterfaceLanguage.SPANISH
PORTUGUESE = InterfaceLanguage.PORTUGUESE


class AlwaysGuesses(LanguageDetector):
    """Answers every text with the same guess, and counts how often it was asked."""

    def __init__(self, guess: LanguageGuess | None) -> None:
        self.guess = guess
        self.calls = 0

    def detect(self, text: str) -> LanguageGuess | None:
        self.calls += 1
        return self.guess


def _policy(guess: LanguageGuess | None) -> tuple[ConversationLanguagePolicy, AlwaysGuesses]:
    detector = AlwaysGuesses(guess)
    return ConversationLanguagePolicy(detector, LanguageConfig(min_words=3, min_confidence=0.8)), (
        detector
    )


def _state(language: InterfaceLanguage | None = None) -> ConversationState:
    return ConversationState(incident_id="I", customer_id=CUSTOMER_ID, language=language)


def test_a_clear_message_overrides_the_hint_and_is_remembered() -> None:
    """Portuguese typed in a Spanish interface is answered, and kept, in Portuguese."""
    policy, _ = _policy(LanguageGuess(language=PORTUGUESE, confidence=0.95))
    state = _state()

    language = policy.resolve(state, "Qual é o meu saldo?", hint=SPANISH)

    assert language == state.language == PORTUGUESE


def test_short_messages_are_never_sent_to_the_detector() -> None:
    """ "1" or an ID would flip the language at random; they keep the current one."""
    policy, detector = _policy(LanguageGuess(language=SPANISH, confidence=0.99))
    state = _state(PORTUGUESE)

    language = policy.resolve(state, "PQR-104233", hint=SPANISH)

    assert language == PORTUGUESE
    assert detector.calls == 0


def test_an_unsure_guess_changes_nothing() -> None:
    """Below the confidence gate, the conversation keeps its language."""
    policy, _ = _policy(LanguageGuess(language=SPANISH, confidence=0.6))
    state = _state(PORTUGUESE)

    assert policy.resolve(state, "hola que tal banco", hint=SPANISH) == PORTUGUESE


def test_without_any_clear_message_the_hint_is_used() -> None:
    """Until the customer writes a clear sentence, the interface's language applies."""
    policy, _ = _policy(None)
    state = _state()

    assert policy.resolve(state, "uno dos tres", hint=PORTUGUESE) == PORTUGUESE
    assert state.language is None


def test_a_later_clear_message_in_the_other_language_switches_it() -> None:
    """A customer who changes language is followed."""
    policy, _ = _policy(LanguageGuess(language=SPANISH, confidence=0.9))
    state = _state(PORTUGUESE)

    assert policy.resolve(state, "ahora quiero mi saldo", hint=PORTUGUESE) == SPANISH
