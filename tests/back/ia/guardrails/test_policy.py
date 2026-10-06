"""Tests the G13 rules: repetition (by text and by request) and confirmed guard flags."""

import pytest

from krtr.back.ia.config import IaConfig
from krtr.back.ia.deterministic.artifacts import ProductType, SlotName
from krtr.back.ia.deterministic.intents import Intent
from krtr.back.ia.guardrails.policy import GuardrailPolicy, request_signature
from krtr.back.ia.matching.artifacts import MatchKind, MatchResult
from krtr.back.ia.matching.config import MatchThresholds
from krtr.back.ia.matching.labels import GuardLabel
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


class FixedConfirmer:
    """Confirms the first flag it is asked about, or none; records every call's labels."""

    def __init__(self, answer: bool | GuardLabel) -> None:
        self.answer = answer
        self.asked: list[list[GuardLabel]] = []

    def confirm_first(
        self,
        state: ConversationState,
        labels: list[GuardLabel],
        reply: str,
        language: InterfaceLanguage,
    ) -> GuardLabel | None:
        self.asked.append(labels)
        if isinstance(self.answer, GuardLabel):
            return self.answer if self.answer in labels else None
        return labels[0] if self.answer else None


def _flagged(*labels: GuardLabel, kind: MatchKind = MatchKind.NO_MATCH) -> MatchResult:
    return MatchResult(kind=kind, candidates=[], guard_flags=list(labels))


@pytest.mark.parametrize(
    ("label", "reason"),
    [
        (GuardLabel.AGGRESSIVE, ClosureReason.AGGRESSIVE),
        (GuardLabel.OFF_TOPIC, ClosureReason.OFF_TOPIC),
    ],
)
def test_a_confirmed_flag_closes_with_its_reason(label: GuardLabel, reason: ClosureReason) -> None:
    """Aggressive or off-topic, once the LLM says yes, ends the conversation (G13)."""
    policy = GuardrailPolicy(IaConfig(), THRESHOLDS, confirmer=FixedConfirmer(True))

    closure = policy.check_flags(_state(), "msg", _flagged(label), SPANISH)

    assert closure is not None and closure.reason == reason


def test_an_unconfirmed_flag_does_not_close() -> None:
    """A "no" from the LLM keeps the conversation open."""
    policy = GuardrailPolicy(IaConfig(), THRESHOLDS, confirmer=FixedConfirmer(False))

    assert policy.check_flags(_state(), "msg", _flagged(GuardLabel.AGGRESSIVE), SPANISH) is None


def test_without_an_llm_flags_never_close() -> None:
    """With `--llm-model none`, behaviour is phase 2's: flag only."""
    assert POLICY.check_flags(_state(), "msg", _flagged(GuardLabel.OFF_TOPIC), SPANISH) is None


def test_a_matched_request_is_answered_even_if_flagged() -> None:
    """An angry customer asking for a balance still gets it; the LLM isn't asked."""
    confirmer = FixedConfirmer(True)
    policy = GuardrailPolicy(IaConfig(), THRESHOLDS, confirmer=confirmer)
    match = _flagged(GuardLabel.AGGRESSIVE, kind=MatchKind.MATCHED)

    assert policy.check_flags(_state(), "msg", match, SPANISH) is None
    assert confirmer.asked == []


def test_unsupported_flags_are_never_sent_for_confirmation() -> None:
    """Unsupported escalates deterministically; it is not a closing flag."""
    confirmer = FixedConfirmer(True)
    policy = GuardrailPolicy(IaConfig(), THRESHOLDS, confirmer=confirmer)

    assert policy.check_flags(_state(), "m", _flagged(GuardLabel.UNSUPPORTED), SPANISH) is None
    assert confirmer.asked == []


def test_every_closing_flag_is_confirmed_in_one_call_and_the_confirmed_one_closes() -> None:
    """Both flags go to the confirmer together (one history read); the confirmed one decides."""
    confirmer = FixedConfirmer(GuardLabel.OFF_TOPIC)
    policy = GuardrailPolicy(IaConfig(), THRESHOLDS, confirmer=confirmer)
    match = _flagged(GuardLabel.UNSUPPORTED, GuardLabel.AGGRESSIVE, GuardLabel.OFF_TOPIC)

    closure = policy.check_flags(_state(), "msg", match, SPANISH)

    assert closure is not None and closure.reason == ClosureReason.OFF_TOPIC
    assert confirmer.asked == [[GuardLabel.AGGRESSIVE, GuardLabel.OFF_TOPIC]]
