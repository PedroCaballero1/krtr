"""Tests whole conversations through the engine: answers, questions, endings and the LLM."""

import pytest

from krtr.back.ia.artifacts import AgentReply, TurnDetails, TurnOutcome, TurnStep, UserTurn
from krtr.back.ia.demo import DEMO_COMPLAINT_ID
from krtr.back.ia.deterministic.intents import Intent
from krtr.back.ia.engine import factory
from krtr.back.ia.engine.engine import ConversationEngine
from krtr.back.ia.matching.artifacts import MatchKind
from krtr.back.ia.matching.labels import GuardLabel
from krtr.back.ia.messages.artifacts import MessageSender
from krtr.back.ia.messages.store import InMemoryMessageStore
from krtr.back.security.oidc.artifacts import InterfaceLanguage
from tests.back.ia.fakes import CUSTOMER_ID, OTHER_CUSTOMER_ID, sample_engine
from tests.back.ia.reasoning.llm.fakes import ScriptedLlm


def _say(
    engine: ConversationEngine,
    text: str,
    language: InterfaceLanguage = InterfaceLanguage.SPANISH,
    customer_id: str = CUSTOMER_ID,
) -> AgentReply:
    turn = UserTurn(incident_id="INC-1", customer_id=customer_id, text=text, language=language)
    return engine.handle(turn)


def test_a_clear_request_is_answered_in_one_turn_in_both_languages() -> None:
    """The fast path: matched intent, slot from the text, answer from the data."""
    spanish = _say(sample_engine(), "Necesito consultar el saldo de mi tarjeta de crédito")
    portuguese = _say(
        sample_engine(),
        "Preciso consultar o saldo do meu cartão de crédito",
        InterfaceLanguage.PORTUGUESE,
    )

    assert spanish.outcome == portuguese.outcome == TurnOutcome.RESOLVED
    assert spanish.reply.startswith(
        "Saldo de tarjeta de crédito:\n- ****9921: saldo 812,300.00 COP"
    )
    assert portuguese.reply.startswith("Saldo de cartão de crédito:\n- ****9921: saldo 812,300.00")


def test_a_missing_product_is_asked_and_the_number_answers_it() -> None:
    """ "What's my balance?" → which product? → "1" → the savings balance."""
    engine = sample_engine()

    question = _say(engine, "¿Cuál es mi saldo?")
    answer = _say(engine, "1")

    assert question.outcome == TurnOutcome.NEEDS_CLARIFICATION
    assert question.reply.splitlines()[1] == "1. cuenta de ahorros"
    assert answer.outcome == TurnOutcome.RESOLVED
    assert answer.reply == "Saldo de cuenta de ahorros:\n- ****7781: 2,350,400.50 COP"


def test_a_complaint_id_given_after_the_question_is_looked_up() -> None:
    """The intent is remembered while the ID is asked for."""
    engine = sample_engine()

    _say(engine, "¿Cómo va mi reclamo?")
    answer = _say(engine, f"es el {DEMO_COMPLAINT_ID.lower()}")

    assert answer.reply == (
        f"Tu caso {DEMO_COMPLAINT_ID} (comisiones), abierto el 2026-09-14, "
        "está en estado: en proceso."
    )


def test_another_customers_complaint_is_answered_as_not_found() -> None:
    """Same reply as a missing ID: the engine never reveals someone else's case (G13)."""
    answer = _say(
        sample_engine(), f"estado de mi queja {DEMO_COMPLAINT_ID}", customer_id=OTHER_CUSTOMER_ID
    )

    assert answer.reply.startswith(f"No encontré un caso {DEMO_COMPLAINT_ID} a tu nombre")


def test_too_many_questions_escalate_and_end_the_conversation() -> None:
    """After 3 unanswerable turns the 4th escalates; later messages get the ended notice."""
    engine = sample_engine()

    outcomes = [_say(engine, text).outcome for text in ("xyz", "qwerty", "zzz", "mmm")]
    after = _say(engine, "¿Cuál es mi saldo?")

    assert outcomes == [TurnOutcome.NEEDS_CLARIFICATION] * 3 + [TurnOutcome.ESCALATED]
    assert after.outcome == TurnOutcome.ESCALATED
    assert after.reply == "Esta conversación ya terminó. Abre un caso nuevo para continuar."


def test_the_same_message_three_times_closes_the_conversation() -> None:
    """Repetition is caught before matching, whatever the message says (G13)."""
    engine = sample_engine()

    outcomes = [_say(engine, "hola banco").outcome for _ in range(3)]

    assert outcomes[-1] == TurnOutcome.CLOSED


def test_the_reply_follows_the_language_the_customer_writes_in() -> None:
    """Portuguese typed in a Spanish interface is answered in Portuguese, short replies too."""
    engine = sample_engine()

    question = _say(engine, "Quero saber o status da minha reclamação")
    answer = _say(engine, DEMO_COMPLAINT_ID)

    assert question.language == answer.language == InterfaceLanguage.PORTUGUESE
    assert answer.reply.startswith(f"Seu caso {DEMO_COMPLAINT_ID} (tarifas)")


def test_a_clear_sentence_in_the_other_language_switches_the_replies() -> None:
    """The customer changes language mid-conversation and the agent follows."""
    engine = sample_engine()

    _say(engine, "Preciso consultar o saldo do meu cartão de crédito")
    switched = _say(engine, "Buenas, quería saber cuál es mi saldo actual en mi cuenta de ahorros")

    assert switched.language == InterfaceLanguage.SPANISH
    assert switched.reply.startswith("Saldo de cuenta de ahorros:")


def test_every_step_of_a_resolved_turn_is_timed() -> None:
    """Each response carries its latency, broken down by step, within its total (G16)."""
    reply = _say(sample_engine(), "Necesito consultar el saldo de mi tarjeta de crédito")

    assert set(reply.timings.steps_ms) == set(TurnStep) - {TurnStep.LLM}  # No LLM selected.
    assert sum(reply.timings.steps_ms.values()) <= reply.timings.total_ms


def test_an_ended_conversation_times_only_what_still_runs() -> None:
    """After a closure nothing is matched or resolved, so those steps are absent."""
    engine = sample_engine()
    for _ in range(3):
        _say(engine, "hola banco")

    reply = _say(engine, "¿Cuál es mi saldo?")

    assert set(reply.timings.steps_ms) == {
        TurnStep.LANGUAGE,
        TurnStep.WRITING,
        TurnStep.PERSISTENCE,
    }


def test_the_reply_reports_what_was_understood_for_the_events_log() -> None:
    """A resolved turn carries its intent and match kind, never needing the reply text (G21)."""
    reply = _say(sample_engine(), "Necesito consultar el saldo de mi tarjeta de crédito")

    assert reply.details == TurnDetails(intent=Intent.ACCOUNT_BALANCE, match_kind=MatchKind.MATCHED)


def test_a_slot_question_reports_the_intent_it_is_filling() -> None:
    """While asking for the product, the intent is already known."""
    reply = _say(sample_engine(), "¿Cuál es mi saldo?")

    assert reply.details.intent == Intent.ACCOUNT_BALANCE


def test_guard_flags_are_reported_without_ending_the_conversation() -> None:
    """An aggressive message is flagged in the metadata; closing on it waits for phase 3."""
    reply = _say(sample_engine(), "Son unos ladrones, no sirven para nada")

    assert reply.details.guard_flags == [GuardLabel.AGGRESSIVE]
    assert reply.outcome != TurnOutcome.CLOSED


def test_a_closure_before_matching_reports_no_match_details() -> None:
    """When a hard rule closes the case, nothing was matched."""
    engine = sample_engine()

    replies = [_say(engine, "hola banco") for _ in range(3)]

    assert replies[-1].details == TurnDetails()


def test_each_turn_stores_the_message_and_the_reply() -> None:
    """The text goes to the messages store, in order, with the turn's language and outcome."""
    messages = InMemoryMessageStore()
    engine = sample_engine(messages)

    reply = _say(engine, "Quero saber o status da minha reclamação")

    stored = messages.list_case(CUSTOMER_ID, "INC-1")
    assert [(item.sender, item.content) for item in stored] == [
        (MessageSender.CUSTOMER, "Quero saber o status da minha reclamação"),
        (MessageSender.AGENT, reply.reply),
    ]
    assert [item.outcome for item in stored] == [None, TurnOutcome.NEEDS_CLARIFICATION]
    assert {item.language for item in stored} == {InterfaceLanguage.PORTUGUESE}
    assert stored[0].sent_at <= stored[1].sent_at


def test_messages_after_the_conversation_ended_are_stored_too() -> None:
    """Every message is kept, even those that only get the ended notice."""
    messages = InMemoryMessageStore()
    engine = sample_engine(messages)
    for _ in range(4):
        _say(engine, "hola banco")

    assert len(messages.list_case(CUSTOMER_ID, "INC-1")) == 8


def test_an_unsupported_request_is_handed_to_a_person_at_once() -> None:
    """A lost card gets the handover message on the first turn, in the customer's language."""
    reply = _say(sample_engine(), "Perdí mi tarjeta y quiero bloquearla")

    assert reply.outcome == TurnOutcome.ESCALATED
    assert reply.reply.startswith("Esa solicitud la atiende un asesor")


def test_with_an_llm_a_free_form_reply_is_answered_and_reported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The LLM reads "la de ahorrar"; the turn says the LLM ran and how long it took."""
    llm = ScriptedLlm({"choice": "savings_account"})  # Only the reply reaches the LLM.
    monkeypatch.setattr(factory, "build_llm_client", lambda *args: llm)
    engine = sample_engine()
    _say(engine, "¿Cuál es mi saldo?")

    reply = _say(engine, "la de ahorrar, porfa")

    assert reply.reply.startswith("Saldo de cuenta de ahorros:")
    assert reply.details.llm_used
    assert TurnStep.LLM in reply.timings.steps_ms


def test_with_an_llm_a_confirmed_off_topic_message_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    """A flagged off-topic message, confirmed, ends with the off-topic closure."""
    llm = ScriptedLlm({"category": "off_topic"})
    monkeypatch.setattr(factory, "build_llm_client", lambda *args: llm)

    reply = _say(sample_engine(), "¿Quién ganó el partido de fútbol ayer?")

    assert reply.outcome == TurnOutcome.CLOSED
    assert reply.reply.startswith("Cerramos esta conversación porque los mensajes no tienen")
