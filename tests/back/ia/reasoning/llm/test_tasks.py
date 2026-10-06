"""Tests the three closed LLM tasks: offered options only, literal values only, and fallbacks."""

import pytest
from pydantic import ValidationError

from krtr.back.ia.deterministic.artifacts import ProductType, SlotName
from krtr.back.ia.matching.labels import GuardLabel
from krtr.back.security.oidc.artifacts import InterfaceLanguage
from tests.back.ia.reasoning.llm.fakes import UNAVAILABLE, ScriptedLlm, tasks_with

SPANISH = InterfaceLanguage.SPANISH
PRODUCTS = [ProductType.SAVINGS_ACCOUNT.value, ProductType.CREDIT_CARD.value]


def test_choose_option_returns_the_option_the_llm_picked() -> None:
    """The reply "la de la tarjeta" reads as the credit card."""
    llm = ScriptedLlm({"choice": "credit_card"})

    choice = tasks_with(llm).choose_option(
        SlotName.PRODUCT_TYPE, PRODUCTS, "la de la tarjeta", SPANISH
    )

    assert choice == ProductType.CREDIT_CARD.value
    assert "tarjeta de crédito" in llm.prompts[0] and "Spanish" in llm.prompts[0]


def test_the_choice_schema_only_admits_the_offered_options() -> None:
    """An option that wasn't offered can't even be produced: it fails validation."""
    llm = ScriptedLlm({"choice": "mortgage"})

    with pytest.raises(ValidationError):
        tasks_with(llm).choose_option(SlotName.PRODUCT_TYPE, PRODUCTS, "la hipoteca", SPANISH)


@pytest.mark.parametrize("answer", [{"choice": "none"}, UNAVAILABLE])
def test_no_choice_or_no_llm_means_no_answer(answer: dict | str) -> None:
    """ "none", or a timeout, leaves the question to be asked again."""
    llm = ScriptedLlm(answer)

    assert tasks_with(llm).choose_option(SlotName.PRODUCT_TYPE, PRODUCTS, "eh", SPANISH) is None


def test_an_extracted_value_must_appear_in_the_text() -> None:
    """The model can't invent a complaint ID: only one the customer wrote is accepted."""
    tasks = tasks_with(ScriptedLlm({"value": "pqr-104233"}, {"value": "PQR-999999"}))

    found = tasks.extract_value(SlotName.COMPLAINT_ID, "es la pqr-104233 de ayer", SPANISH)
    invented = tasks.extract_value(SlotName.COMPLAINT_ID, "mi queja de ayer", SPANISH)

    assert found == "PQR-104233"
    assert invented is None


def test_fill_slot_offers_options_for_closed_slots_and_extracts_free_ones() -> None:
    """The same entry point serves the resolver and the clarifier."""
    llm = ScriptedLlm({"choice": "savings_account"}, {"value": "PQR-1"})
    tasks = tasks_with(llm)

    assert tasks.fill_slot(SlotName.PRODUCT_TYPE, PRODUCTS, "la de mis ahorros", SPANISH) == (
        "savings_account"
    )
    assert tasks.fill_slot(SlotName.COMPLAINT_ID, [], "caso PQR-1", SPANISH) == "PQR-1"


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ({"category": "abusive"}, True),
        ({"category": "banking"}, False),
        ({"category": "off_topic"}, False),
        (UNAVAILABLE, False),
    ],
)
def test_a_guard_is_confirmed_only_by_its_own_category(answer: dict | str, expected: bool) -> None:
    """An angry banking message is "banking": never closed; nor without an LLM."""
    llm = ScriptedLlm(answer)

    confirmed = tasks_with(llm).confirm_guard(GuardLabel.AGGRESSIVE, "son unos inútiles", SPANISH)

    assert confirmed is expected


@pytest.mark.parametrize(
    ("reply", "accepted"),
    [
        ("la de la tarjeta, la de crédito", True),  # Credit card overlaps most: 2 stems.
        ("la de la tarjeta, no la otra", False),  # Credit and debit tie on "tarjeta".
        ("mi plástico de crédito", False),  # Card and mortgage tie on "crédito" in Spanish.
    ],
)
def test_a_closed_slot_choice_must_be_singled_out_by_the_reply(reply: str, accepted: bool) -> None:
    """The LLM's pick stands only if the reply points at it more than at any other option."""
    every_product = [member.value for member in ProductType]
    llm = ScriptedLlm({"choice": "credit_card"})

    value = tasks_with(llm).fill_slot(SlotName.PRODUCT_TYPE, every_product, reply, SPANISH)

    assert (value == ProductType.CREDIT_CARD.value) is accepted
