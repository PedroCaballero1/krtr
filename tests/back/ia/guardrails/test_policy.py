"""Tests the deterministic repetition rule (G13)."""

from krtr.back.ia.config import IaConfig
from krtr.back.ia.guardrails.policy import GuardrailPolicy
from krtr.back.ia.reasoning.artifacts import ClosureReason, ConversationState
from tests.back.ia.fakes import CUSTOMER_ID

POLICY = GuardrailPolicy(IaConfig(repetition_limit=3))


def _state(*recent: str) -> ConversationState:
    return ConversationState(incident_id="I", customer_id=CUSTOMER_ID, recent_messages=list(recent))


def test_the_limit_th_repeat_closes_the_conversation() -> None:
    """Twice before plus this one reaches the limit of 3, even typed differently."""
    closure = POLICY.check(_state("hola banco", "hola banco"), "¡Hola, BANCO!")

    assert closure is not None
    assert closure.reason == ClosureReason.REPETITIVE


def test_below_the_limit_nothing_happens() -> None:
    """One earlier repeat is normal (the customer may resend once)."""
    assert POLICY.check(_state("hola banco", "saldo"), "hola banco") is None


def test_option_numbers_never_count_as_repetition() -> None:
    """Answering "1" to several questions is how the flow works, not spam."""
    assert POLICY.check(_state("1", "1"), "1") is None
