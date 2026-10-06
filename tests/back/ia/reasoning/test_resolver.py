"""Tests how the resolver combines matching, slot filling and the clarification limit."""

from krtr.back.ia.config import IaConfig
from krtr.back.ia.deterministic.artifacts import ProductType, SlotName
from krtr.back.ia.deterministic.intents import Intent
from krtr.back.ia.matching.artifacts import MatchCandidate, MatchKind, MatchResult
from krtr.back.ia.matching.labels import GuardLabel
from krtr.back.ia.reasoning.artifacts import (
    ConversationState,
    Escalated,
    EscalationReason,
    PendingQuestion,
    QuestionKind,
    Resolved,
)
from krtr.back.ia.reasoning.clarifier import TemplateClarifier
from krtr.back.ia.reasoning.resolver import TurnResolver
from krtr.back.security.oidc.artifacts import InterfaceLanguage
from tests.back.ia.fakes import CUSTOMER_ID, sample_registry

SPANISH = InterfaceLanguage.SPANISH
REGISTRY = sample_registry()
RESOLVER = TurnResolver(REGISTRY, TemplateClarifier(REGISTRY), IaConfig(max_clarification_turns=2))
CANDIDATES = [
    MatchCandidate(intent=Intent.ACCOUNT_BALANCE, score=0.9),
    MatchCandidate(intent=Intent.COMPLAINT_STATUS, score=0.1),
]
BALANCE = MatchResult(kind=MatchKind.MATCHED, candidates=CANDIDATES)
NO_MATCH = MatchResult(kind=MatchKind.NO_MATCH, candidates=CANDIDATES)


def _state(attempts: int = 0) -> ConversationState:
    return ConversationState(
        incident_id="I", customer_id=CUSTOMER_ID, clarification_attempts=attempts
    )


def test_a_clear_match_with_its_slot_resolves_without_asking() -> None:
    """The deterministic fast path: no question, straight to the action."""
    resolution = RESOLVER.resolve(_state(), "saldo de mi tarjeta de crédito", BALANCE, SPANISH)

    assert resolution == Resolved(
        intent=Intent.ACCOUNT_BALANCE, slots={SlotName.PRODUCT_TYPE: ProductType.CREDIT_CARD.value}
    )


def test_a_clear_match_without_its_slot_asks_for_it_with_options() -> None:
    """A closed slot is offered as a numbered list, remembering the intent."""
    resolution = RESOLVER.resolve(_state(), "cuál es mi saldo", BALANCE, SPANISH)

    question = resolution.question
    assert question.kind == QuestionKind.CHOOSE_OPTION
    assert (question.intent, question.slot) == (Intent.ACCOUNT_BALANCE, SlotName.PRODUCT_TYPE)
    assert question.options == [member.value for member in ProductType]


def test_a_free_slot_is_asked_to_be_typed() -> None:
    """A complaint ID has no options to offer."""
    match = MatchResult(kind=MatchKind.MATCHED, candidates=CANDIDATES[::-1])

    resolution = RESOLVER.resolve(_state(), "cómo va mi queja", match, SPANISH)

    assert resolution.question.kind == QuestionKind.PROVIDE_SLOT
    assert resolution.question.slot == SlotName.COMPLAINT_ID


def test_the_question_after_the_limit_escalates_instead() -> None:
    """With 2 questions already asked and a limit of 2, the third becomes a handoff (G20)."""
    resolution = RESOLVER.resolve(_state(attempts=2), "nada que ver", NO_MATCH, SPANISH)

    assert resolution == Escalated(reason=EscalationReason.CLARIFICATION_LIMIT)


def test_an_answer_at_the_limit_still_resolves() -> None:
    """The limit stops questions, not answers."""
    resolution = RESOLVER.resolve(
        _state(attempts=2), "saldo de mi cuenta de ahorros", BALANCE, SPANISH
    )

    assert isinstance(resolution, Resolved)


UNSUPPORTED = MatchResult(
    kind=MatchKind.NO_MATCH,
    candidates=CANDIDATES,
    guard_flags=[GuardLabel.UNSUPPORTED],
    top_label=GuardLabel.UNSUPPORTED,
)


def test_an_unsupported_request_goes_straight_to_a_person() -> None:
    """A lost card is escalated at once: no "rephrase", no waiting for 3 questions (G20)."""
    resolution = RESOLVER.resolve(_state(), "perdí mi tarjeta", UNSUPPORTED, SPANISH)

    assert resolution == Escalated(reason=EscalationReason.UNSUPPORTED_REQUEST)


def test_unsupported_only_escalates_when_it_is_the_best_label() -> None:
    """Flagged, but an intent scores higher: the normal flow decides."""
    match = UNSUPPORTED.model_copy(update={"top_label": Intent.ACCOUNT_BALANCE})

    resolution = RESOLVER.resolve(_state(), "algo de mi tarjeta", match, SPANISH)

    assert not isinstance(resolution, Escalated)


def test_a_pending_question_is_answered_before_an_unsupported_escalation() -> None:
    """ "La 3" to the product question is an answer, even if the matcher flags unsupported."""
    question = PendingQuestion(
        kind=QuestionKind.CHOOSE_OPTION,
        intent=Intent.ACCOUNT_BALANCE,
        slot=SlotName.PRODUCT_TYPE,
        options=[member.value for member in ProductType],
    )
    state = ConversationState(incident_id="I", customer_id=CUSTOMER_ID, pending=question)

    resolution = RESOLVER.resolve(state, "la 3", UNSUPPORTED, SPANISH)

    assert resolution.slots == {SlotName.PRODUCT_TYPE: ProductType.CREDIT_CARD.value}


def test_a_pending_question_the_reply_does_not_answer_still_escalates_unsupported() -> None:
    """A lost card mentioned mid-question goes to a person."""
    question = PendingQuestion(kind=QuestionKind.REPHRASE)
    state = ConversationState(incident_id="I", customer_id=CUSTOMER_ID, pending=question)

    resolution = RESOLVER.resolve(state, "perdí mi tarjeta", UNSUPPORTED, SPANISH)

    assert resolution == Escalated(reason=EscalationReason.UNSUPPORTED_REQUEST)
