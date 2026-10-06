"""Tests how the resolver combines matching, slot filling and the clarification limit."""

from krtr.back.ia.config import IaConfig
from krtr.back.ia.deterministic.artifacts import ProductType, SlotName
from krtr.back.ia.deterministic.intents import Intent
from krtr.back.ia.matching.artifacts import MatchCandidate, MatchKind, MatchResult
from krtr.back.ia.reasoning.artifacts import (
    ConversationState,
    Escalated,
    EscalationReason,
    QuestionKind,
    Resolved,
)
from krtr.back.ia.reasoning.clarifier import TemplateClarifier
from krtr.back.ia.reasoning.resolver import TurnResolver
from tests.back.ia.fakes import CUSTOMER_ID, sample_registry

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
    resolution = RESOLVER.resolve(_state(), "saldo de mi tarjeta de crédito", BALANCE)

    assert resolution == Resolved(
        intent=Intent.ACCOUNT_BALANCE, slots={SlotName.PRODUCT_TYPE: ProductType.CREDIT_CARD.value}
    )


def test_a_clear_match_without_its_slot_asks_for_it_with_options() -> None:
    """A closed slot is offered as a numbered list, remembering the intent."""
    resolution = RESOLVER.resolve(_state(), "cuál es mi saldo", BALANCE)

    question = resolution.question
    assert question.kind == QuestionKind.CHOOSE_OPTION
    assert (question.intent, question.slot) == (Intent.ACCOUNT_BALANCE, SlotName.PRODUCT_TYPE)
    assert question.options == [member.value for member in ProductType]


def test_a_free_slot_is_asked_to_be_typed() -> None:
    """A complaint ID has no options to offer."""
    match = MatchResult(kind=MatchKind.MATCHED, candidates=CANDIDATES[::-1])

    resolution = RESOLVER.resolve(_state(), "cómo va mi queja", match)

    assert resolution.question.kind == QuestionKind.PROVIDE_SLOT
    assert resolution.question.slot == SlotName.COMPLAINT_ID


def test_the_question_after_the_limit_escalates_instead() -> None:
    """With 2 questions already asked and a limit of 2, the third becomes a handoff (G20)."""
    resolution = RESOLVER.resolve(_state(attempts=2), "nada que ver", NO_MATCH)

    assert resolution == Escalated(reason=EscalationReason.CLARIFICATION_LIMIT)


def test_an_answer_at_the_limit_still_resolves() -> None:
    """The limit stops questions, not answers."""
    resolution = RESOLVER.resolve(_state(attempts=2), "saldo de mi cuenta de ahorros", BALANCE)

    assert isinstance(resolution, Resolved)
