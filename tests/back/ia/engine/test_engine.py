"""Tests whole conversations through the phase 1 engine: answers, questions and endings."""

from krtr.back.ia.artifacts import AgentReply, TurnOutcome, UserTurn
from krtr.back.ia.demo import DEMO_COMPLAINT_ID
from krtr.back.ia.engine.engine import ConversationEngine
from krtr.back.security.oidc.artifacts import InterfaceLanguage
from tests.back.ia.fakes import CUSTOMER_ID, OTHER_CUSTOMER_ID, sample_engine


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
