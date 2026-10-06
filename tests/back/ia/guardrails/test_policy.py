"""Tests the deterministic repetition rules (G13): by similar text and by the same request."""

from krtr.back.ia.config import IaConfig
from krtr.back.ia.deterministic.artifacts import ProductType, SlotName
from krtr.back.ia.deterministic.intents import Intent
from krtr.back.ia.guardrails.policy import GuardrailPolicy, request_signature
from krtr.back.ia.matching.config import MatchThresholds
from krtr.back.ia.reasoning.artifacts import ClosureReason, ConversationState, Resolved
from krtr.back.security.oidc.artifacts import InterfaceLanguage
from tests.back.ia.fakes import CUSTOMER_ID, unit

SPANISH = InterfaceLanguage.SPANISH
THRESHOLDS = {language: MatchThresholds(repeat=0.9) for language in InterfaceLanguage}
POLICY = GuardrailPolicy(IaConfig(repetition_limit=3), THRESHOLDS)
HELLO = unit(1, 0, 0)
NEAR_HELLO = unit(1, 0.2, 0)  # Similarity 0.98 with HELLO: the same message, reworded.
BALANCE = unit(0, 1, 0)


def _state(*recent: object, requests: list[str] | None = None) -> ConversationState:
    return ConversationState(
        incident_id="I",
        customer_id=CUSTOMER_ID,
        recent_embeddings=[vector.tolist() for vector in recent],
        recent_requests=requests or [],
    )


def _savings(*, product: ProductType = ProductType.SAVINGS_ACCOUNT) -> Resolved:
    return Resolved(intent=Intent.ACCOUNT_BALANCE, slots={SlotName.PRODUCT_TYPE: product.value})


def test_a_reworded_message_counts_as_a_repeat_even_if_not_back_to_back() -> None:
    """Two earlier near-identical messages, with another one between them, reach the limit."""
    closure = POLICY.check(_state(HELLO, BALANCE, NEAR_HELLO), "hola, banco", HELLO, SPANISH)

    assert closure is not None
    assert closure.reason == ClosureReason.REPETITIVE


def test_below_the_limit_nothing_happens() -> None:
    """One earlier repeat is normal (the customer may resend once)."""
    assert POLICY.check(_state(HELLO, BALANCE), "hola banco", HELLO, SPANISH) is None


def test_different_messages_are_not_repeats() -> None:
    """Below the `repeat` similarity, messages are new ones."""
    assert POLICY.check(_state(BALANCE, BALANCE), "hola banco", HELLO, SPANISH) is None


def test_option_numbers_never_count_as_repetition() -> None:
    """Answering "1" to several questions is how the flow works, not spam."""
    assert POLICY.check(_state(HELLO, HELLO), "1", HELLO, SPANISH) is None


def test_the_same_request_reached_three_times_is_a_repeat_whatever_the_wording() -> None:
    """Same intent and same product, twice before: the third time closes the case."""
    signature = request_signature(_savings())

    closure = POLICY.check_request(_state(requests=[signature, "other", signature]), _savings())

    assert closure is not None
    assert closure.reason == ClosureReason.REPETITIVE


def test_the_same_request_for_another_product_is_a_new_question() -> None:
    """A balance for the card after two savings balances is not a repeat."""
    signature = request_signature(_savings())
    card = _savings(product=ProductType.CREDIT_CARD)

    assert POLICY.check_request(_state(requests=[signature, signature]), card) is None


def test_the_signature_ignores_the_order_of_the_slots() -> None:
    """Two resolutions with the same slots in another order are the same request."""
    first = Resolved(intent=Intent.ACCOUNT_BALANCE, slots={"a": "1", "b": "2"})
    second = Resolved(intent=Intent.ACCOUNT_BALANCE, slots={"b": "2", "a": "1"})

    assert request_signature(first) == request_signature(second)
