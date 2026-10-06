"""Tests the template clarifier: what it asks, and how it reads the replies."""

from krtr.back.ia.deterministic.artifacts import ProductType, SlotName
from krtr.back.ia.deterministic.intents import Intent
from krtr.back.ia.matching.artifacts import MatchCandidate, MatchKind, MatchResult
from krtr.back.ia.reasoning.artifacts import (
    ConversationState,
    NeedsClarification,
    PendingQuestion,
    QuestionKind,
    Resolved,
)
from krtr.back.ia.reasoning.clarifier import TemplateClarifier
from krtr.back.security.oidc.artifacts import InterfaceLanguage
from tests.back.ia.fakes import CUSTOMER_ID, sample_registry

SPANISH = InterfaceLanguage.SPANISH
CLARIFIER = TemplateClarifier(sample_registry())
CANDIDATES = [
    MatchCandidate(intent=Intent.COMPLAINT_STATUS, score=0.5),
    MatchCandidate(intent=Intent.ACCOUNT_BALANCE, score=0.4),
]
AMBIGUOUS = MatchResult(kind=MatchKind.AMBIGUOUS, candidates=CANDIDATES)
NO_MATCH = MatchResult(kind=MatchKind.NO_MATCH, candidates=CANDIDATES)
BALANCE_MATCH = MatchResult(kind=MatchKind.MATCHED, candidates=CANDIDATES[::-1])


def _waiting_for(question: PendingQuestion) -> ConversationState:
    return ConversationState(incident_id="I", customer_id=CUSTOMER_ID, pending=question)


def _intent_question() -> PendingQuestion:
    return CLARIFIER.ask(AMBIGUOUS).question


def _product_question() -> PendingQuestion:
    return PendingQuestion(
        kind=QuestionKind.CHOOSE_OPTION,
        intent=Intent.ACCOUNT_BALANCE,
        slot=SlotName.PRODUCT_TYPE,
        options=[member.value for member in ProductType],
    )


def test_ambiguous_offers_the_candidates_in_score_order() -> None:
    """The customer chooses among what the matcher found plausible."""
    question = _intent_question()

    assert question.kind == QuestionKind.CHOOSE_INTENT
    assert question.options == [Intent.COMPLAINT_STATUS.value, Intent.ACCOUNT_BALANCE.value]


def test_no_match_asks_to_rephrase() -> None:
    """With nothing plausible, offering options would be guessing."""
    assert CLARIFIER.ask(NO_MATCH).question.kind == QuestionKind.REPHRASE


def test_an_option_number_picks_the_intent() -> None:
    """ "2" is the second option offered."""
    resolution = CLARIFIER.interpret(_waiting_for(_intent_question()), "la 2", NO_MATCH, SPANISH)

    assert resolution == Resolved(intent=Intent.ACCOUNT_BALANCE)


def test_a_slot_option_keeps_what_was_collected() -> None:
    """Picking the product completes the slot filling in progress."""
    question = _product_question()
    question.collected = {"earlier": "value"}

    resolution = CLARIFIER.interpret(_waiting_for(question), "3", NO_MATCH, SPANISH)

    assert resolution == Resolved(
        intent=Intent.ACCOUNT_BALANCE,
        slots={"earlier": "value", SlotName.PRODUCT_TYPE: ProductType.CREDIT_CARD.value},
    )


def test_a_slot_can_be_named_instead_of_numbered() -> None:
    """ "La de ahorros" answers the product question as well as "1"."""
    resolution = CLARIFIER.interpret(
        _waiting_for(_product_question()), "la de ahorros", NO_MATCH, SPANISH
    )

    assert resolution.slots == {SlotName.PRODUCT_TYPE: ProductType.SAVINGS_ACCOUNT.value}


def test_a_free_slot_is_read_with_the_actions_rule() -> None:
    """A complaint ID typed as the answer fills the slot."""
    question = PendingQuestion(
        kind=QuestionKind.PROVIDE_SLOT, intent=Intent.COMPLAINT_STATUS, slot=SlotName.COMPLAINT_ID
    )

    resolution = CLARIFIER.interpret(_waiting_for(question), "pqr-104233", NO_MATCH, SPANISH)

    assert resolution == Resolved(
        intent=Intent.COMPLAINT_STATUS, slots={SlotName.COMPLAINT_ID: "PQR-104233"}
    )


def test_a_clear_new_request_replaces_the_pending_question() -> None:
    """The customer changed their mind: a clearly matched message wins."""
    resolution = CLARIFIER.interpret(
        _waiting_for(_intent_question()), "mi saldo", BALANCE_MATCH, SPANISH
    )

    assert resolution == Resolved(intent=Intent.ACCOUNT_BALANCE)


def test_an_unreadable_reply_repeats_the_question() -> None:
    """An answer that fits nothing gets the same question, not a new guess."""
    question = _intent_question()

    resolution = CLARIFIER.interpret(_waiting_for(question), "9", NO_MATCH, SPANISH)

    assert resolution == NeedsClarification(question=question)


def test_after_a_rephrase_request_the_reply_is_read_as_a_new_message() -> None:
    """A rephrased but still ambiguous message gets the candidates this time."""
    question = PendingQuestion(kind=QuestionKind.REPHRASE)

    resolution = CLARIFIER.interpret(
        _waiting_for(question), "algo de mi cuenta", AMBIGUOUS, SPANISH
    )

    assert resolution.question.kind == QuestionKind.CHOOSE_INTENT
