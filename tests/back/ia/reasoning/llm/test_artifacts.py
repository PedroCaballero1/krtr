"""Tests the transcript the LLM reads: how it is written into a prompt and read for grounding."""

from krtr.back.ia.messages.artifacts import MessageSender
from tests.back.ia.reasoning.llm.fakes import NO_HISTORY, transcript

CUSTOMER, AGENT = MessageSender.CUSTOMER, MessageSender.AGENT


def test_an_empty_transcript_renders_nothing() -> None:
    """No earlier messages, no lines."""
    assert NO_HISTORY.render() == ""


def test_each_message_is_one_role_line_and_a_numbered_question_stays_under_its_role() -> None:
    """A multi-line agent question is indented, so its options can't pass for a customer line."""
    history = transcript(
        (CUSTOMER, "  quiero mi saldo "),
        (AGENT, "¿Sobre qué producto?\n1. cuenta de ahorros\n2. cuenta corriente"),
    )

    assert history.render() == (
        "Customer: quiero mi saldo\n"
        "Agent: ¿Sobre qué producto?\n"
        "  1. cuenta de ahorros\n"
        "  2. cuenta corriente"
    )


def test_customer_texts_are_the_customers_own_words_newest_first() -> None:
    """Grounding reads only what the customer wrote, the latest first."""
    history = transcript(
        (CUSTOMER, "primero"), (AGENT, "pregunta"), (CUSTOMER, "segundo"), (AGENT, "otra")
    )

    assert history.customer_texts() == ["segundo", "primero"]
