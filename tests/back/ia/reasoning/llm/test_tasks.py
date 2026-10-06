"""Tests the three closed LLM tasks: offered options only, literal values only, in context."""

import pytest
from pydantic import ValidationError

from krtr.back.ia.deterministic.artifacts import ProductType, SlotName
from krtr.back.ia.matching.labels import GuardLabel
from krtr.back.ia.messages.artifacts import MessageSender
from krtr.back.security.oidc.artifacts import InterfaceLanguage
from tests.back.ia.reasoning.llm.fakes import (
    NO_HISTORY,
    UNAVAILABLE,
    ScriptedLlm,
    tasks_with,
    transcript,
)

SPANISH = InterfaceLanguage.SPANISH
PRODUCTS = [ProductType.SAVINGS_ACCOUNT.value, ProductType.CREDIT_CARD.value]


def test_choose_option_returns_the_option_the_llm_picked() -> None:
    """The reply "la de la tarjeta" reads as the credit card."""
    llm = ScriptedLlm({"choice": "credit_card"})

    choice = tasks_with(llm).choose_option(
        SlotName.PRODUCT_TYPE, PRODUCTS, "la de la tarjeta", NO_HISTORY, SPANISH
    )

    assert choice == ProductType.CREDIT_CARD.value
    assert "tarjeta de crédito" in llm.prompts[0] and "Spanish" in llm.prompts[0]


def test_the_choice_schema_only_admits_the_offered_options() -> None:
    """An option that wasn't offered can't even be produced: it fails validation."""
    llm = ScriptedLlm({"choice": "mortgage"})

    with pytest.raises(ValidationError):
        tasks_with(llm).choose_option(
            SlotName.PRODUCT_TYPE, PRODUCTS, "la hipoteca", NO_HISTORY, SPANISH
        )


@pytest.mark.parametrize("answer", [{"choice": "none"}, UNAVAILABLE])
def test_no_choice_or_no_llm_means_no_answer(answer: dict | str) -> None:
    """ "none", or a timeout, leaves the question to be asked again."""
    llm = ScriptedLlm(answer)

    choice = tasks_with(llm).choose_option(
        SlotName.PRODUCT_TYPE, PRODUCTS, "eh", NO_HISTORY, SPANISH
    )

    assert choice is None


def test_an_extracted_value_must_appear_in_the_text() -> None:
    """The model can't invent a complaint ID: only one the customer wrote is accepted."""
    tasks = tasks_with(ScriptedLlm({"value": "pqr-104233"}, {"value": "PQR-999999"}))

    found = tasks.extract_value(
        SlotName.COMPLAINT_ID, "es la pqr-104233 de ayer", NO_HISTORY, SPANISH
    )
    invented = tasks.extract_value(SlotName.COMPLAINT_ID, "mi queja de ayer", NO_HISTORY, SPANISH)

    assert found == "PQR-104233"
    assert invented is None


def test_fill_slot_offers_options_for_closed_slots_and_extracts_free_ones() -> None:
    """The same entry point serves the resolver and the clarifier."""
    llm = ScriptedLlm({"choice": "savings_account"}, {"value": "PQR-1"})
    tasks = tasks_with(llm)

    product = tasks.fill_slot(
        SlotName.PRODUCT_TYPE, PRODUCTS, "la de mis ahorros", NO_HISTORY, SPANISH
    )
    complaint = tasks.fill_slot(SlotName.COMPLAINT_ID, [], "caso PQR-1", NO_HISTORY, SPANISH)

    assert product == "savings_account"
    assert complaint == "PQR-1"


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

    confirmed = tasks_with(llm).confirm_guard(
        GuardLabel.AGGRESSIVE, "son unos inútiles", NO_HISTORY, SPANISH
    )

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

    value = tasks_with(llm).fill_slot(
        SlotName.PRODUCT_TYPE, every_product, reply, NO_HISTORY, SPANISH
    )

    assert (value == ProductType.CREDIT_CARD.value) is accepted


EVERY_PRODUCT = [member.value for member in ProductType]
CUSTOMER, AGENT = MessageSender.CUSTOMER, MessageSender.AGENT
PRODUCT_QUESTION_TEXT = "¿Sobre qué producto? Responde con el número:\n1. cuenta de ahorros"


def test_every_task_shows_the_conversation_before_the_reply() -> None:
    """The prompt carries the earlier messages, oldest first, and the reply is read last."""
    history = transcript((CUSTOMER, "quiero mi saldo"), (AGENT, PRODUCT_QUESTION_TEXT))
    llm = ScriptedLlm({"choice": "none"}, {"value": None}, {"category": "banking"})
    tasks = tasks_with(llm)

    tasks.choose_option(SlotName.PRODUCT_TYPE, PRODUCTS, "esa", history, SPANISH)
    tasks.extract_value(SlotName.COMPLAINT_ID, "esa", history, SPANISH)
    tasks.confirm_guard(GuardLabel.AGGRESSIVE, "esa", history, SPANISH)

    for prompt in llm.prompts:
        assert "Customer: quiero mi saldo\nAgent: ¿Sobre qué producto?" in prompt
        assert prompt.index("Customer: quiero mi saldo") < prompt.index('"esa"')


def test_without_history_the_prompt_has_no_context_section() -> None:
    """The first doubtful turn of a case gets the prompt measured before history existed."""
    llm = ScriptedLlm({"choice": "none"}, {"value": None}, {"category": "banking"})
    tasks = tasks_with(llm)

    tasks.choose_option(SlotName.PRODUCT_TYPE, PRODUCTS, "esa", NO_HISTORY, SPANISH)
    tasks.extract_value(SlotName.COMPLAINT_ID, "esa", NO_HISTORY, SPANISH)
    tasks.confirm_guard(GuardLabel.AGGRESSIVE, "esa", NO_HISTORY, SPANISH)

    second_lines = [prompt.splitlines()[1] for prompt in llm.prompts]
    assert second_lines == [
        "The customer was asked: which producto they mean",
        "Find the número de caso in the message.",
        "",
    ]


def test_a_value_the_customer_wrote_earlier_is_accepted_but_not_one_the_agent_wrote() -> None:
    """ "La que te di antes" points at the customer's ID; an ID only the agent wrote is invented."""
    customer_gave_it = transcript(
        (CUSTOMER, "mi caso es el PQR-104233"), (AGENT, "Indícame el número.")
    )
    agent_wrote_it = transcript((AGENT, "No encontré un caso PQR-555 a tu nombre."))
    tasks = tasks_with(ScriptedLlm({"value": "PQR-104233"}, {"value": "PQR-555"}))

    earlier = tasks.extract_value(
        SlotName.COMPLAINT_ID, "la que te di antes", customer_gave_it, SPANISH
    )
    from_agent = tasks.extract_value(SlotName.COMPLAINT_ID, "esa", agent_wrote_it, SPANISH)

    assert earlier == "PQR-104233"
    assert from_agent is None


@pytest.mark.parametrize(
    ("history", "reply", "accepted"),
    [
        # The reply ties the two cards; the customer's earlier message breaks the tie.
        (((CUSTOMER, "el saldo de mi tarjeta de crédito"),), "la de la tarjeta", True),
        # A reply that names no product is read through the earlier message.
        (((CUSTOMER, "tengo una tarjeta de crédito"),), "esa misma", True),
        # The newest earlier message decides over an older one.
        (
            ((CUSTOMER, "uso la tarjeta de débito"), (CUSTOMER, "y la tarjeta de crédito")),
            "la de la tarjeta",
            True,
        ),
        # The agent's question lists every option: it never singles one out.
        (((AGENT, PRODUCT_QUESTION_TEXT + "\n3. tarjeta de crédito"),), "la de la tarjeta", False),
        # The latest reply wins: it singles out debit, so credit from the history is rejected.
        (((CUSTOMER, "mi tarjeta de crédito"),), "la de débito", False),
        # Nothing in the conversation singles out an option.
        (((CUSTOMER, "hola"),), "la de la tarjeta", False),
    ],
)
def test_a_closed_slot_choice_may_be_singled_out_by_the_customers_earlier_words(
    history: tuple[tuple[MessageSender, str], ...], reply: str, accepted: bool
) -> None:
    """Earlier customer messages only break the reply's ties; the agent's words never count."""
    llm = ScriptedLlm({"choice": "credit_card"})

    value = tasks_with(llm).fill_slot(
        SlotName.PRODUCT_TYPE, EVERY_PRODUCT, reply, transcript(*history), SPANISH
    )

    assert (value == ProductType.CREDIT_CARD.value) is accepted
