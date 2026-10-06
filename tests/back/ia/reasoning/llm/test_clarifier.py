"""Tests the clarifier chain: the template clarifier first, the LLM only for unreadable replies."""

from krtr.back.ia.deterministic.artifacts import ProductType, SlotName
from krtr.back.ia.deterministic.intents import Intent
from krtr.back.ia.matching.artifacts import MatchCandidate, MatchKind, MatchResult
from krtr.back.ia.messages.artifacts import MessageSender
from krtr.back.ia.messages.store import InMemoryMessageStore
from krtr.back.ia.reasoning.artifacts import (
    ConversationState,
    NeedsClarification,
    PendingQuestion,
    QuestionKind,
    Resolved,
)
from krtr.back.ia.reasoning.clarifier import TemplateClarifier
from krtr.back.ia.reasoning.llm.clarifier import LlmClarifier
from krtr.back.ia.reasoning.llm.config import HistoryConfig
from krtr.back.ia.reasoning.llm.history import ConversationHistory
from krtr.back.security.oidc.artifacts import InterfaceLanguage
from tests.back.ia.fakes import CUSTOMER_ID, sample_registry
from tests.back.ia.reasoning.llm.fakes import (
    UNAVAILABLE,
    CountingMessageStore,
    ScriptedLlm,
    stored_message,
    tasks_with,
)

SPANISH = InterfaceLanguage.SPANISH
NO_MATCH = MatchResult(
    kind=MatchKind.NO_MATCH, candidates=[MatchCandidate(intent=Intent.ACCOUNT_BALANCE, score=0)]
)
PRODUCT_QUESTION = PendingQuestion(
    kind=QuestionKind.CHOOSE_OPTION,
    intent=Intent.ACCOUNT_BALANCE,
    slot=SlotName.PRODUCT_TYPE,
    options=[member.value for member in ProductType],
)


def _clarifier(llm: ScriptedLlm, messages: InMemoryMessageStore | None = None) -> LlmClarifier:
    registry = sample_registry()
    history = ConversationHistory(messages or InMemoryMessageStore(), HistoryConfig())
    return LlmClarifier(TemplateClarifier(registry), tasks_with(llm), registry, history)


def _state(question: PendingQuestion) -> ConversationState:
    return ConversationState(incident_id="I", customer_id=CUSTOMER_ID, pending=question)


def test_a_reply_the_template_reads_never_reaches_the_llm() -> None:
    """ "3" is the template clarifier's job: no LLM call, no history read, no latency."""
    llm = ScriptedLlm()
    messages = CountingMessageStore()

    resolution = _clarifier(llm, messages).interpret(
        _state(PRODUCT_QUESTION), "3", NO_MATCH, SPANISH
    )

    assert resolution.slots[SlotName.PRODUCT_TYPE] == ProductType.CREDIT_CARD.value
    assert llm.prompts == []
    assert messages.reads == 0


def test_a_free_form_reply_is_read_by_the_llm_against_the_offered_options() -> None:
    """ "La de la tarjeta, la de crédito" settles the product the rules couldn't."""
    llm = ScriptedLlm({"choice": "credit_card"})

    resolution = _clarifier(llm).interpret(
        _state(PRODUCT_QUESTION), "la de la tarjeta, la de crédito", NO_MATCH, SPANISH
    )

    assert resolution == Resolved(
        intent=Intent.ACCOUNT_BALANCE,
        slots={SlotName.PRODUCT_TYPE: ProductType.CREDIT_CARD.value},
    )


def test_an_intent_choice_is_read_too() -> None:
    """A reply to "what do you need?" maps to one of the offered intents."""
    question = PendingQuestion(
        kind=QuestionKind.CHOOSE_INTENT,
        options=[Intent.ACCOUNT_BALANCE.value, Intent.COMPLAINT_STATUS.value],
    )
    llm = ScriptedLlm({"choice": "complaint_status"})

    resolution = _clarifier(llm).interpret(_state(question), "lo del reclamo", NO_MATCH, SPANISH)

    assert resolution == Resolved(intent=Intent.COMPLAINT_STATUS)


def test_when_the_llm_sees_no_answer_or_is_down_the_question_is_repeated() -> None:
    """The deterministic answer stands: the same question again."""
    for answer in ({"choice": "none"}, UNAVAILABLE):
        resolution = _clarifier(ScriptedLlm(answer)).interpret(
            _state(PRODUCT_QUESTION), "mmm no sé", NO_MATCH, SPANISH
        )

        assert resolution == NeedsClarification(question=PRODUCT_QUESTION)


def test_a_rephrase_request_is_never_sent_to_the_llm() -> None:
    """With no options offered, there is nothing for the LLM to choose from."""
    llm = ScriptedLlm()
    question = PendingQuestion(kind=QuestionKind.REPHRASE)

    _clarifier(llm).interpret(_state(question), "blablabla", NO_MATCH, SPANISH)

    assert llm.prompts == []


def test_a_choice_the_reply_does_not_single_out_is_rejected() -> None:
    """ "La de la tarjeta" fits credit and debit cards: the LLM's pick is a guess, so ask again."""
    llm = ScriptedLlm({"choice": "credit_card"})

    resolution = _clarifier(llm).interpret(
        _state(PRODUCT_QUESTION), "la de la tarjeta, no la otra", NO_MATCH, SPANISH
    )

    assert resolution == NeedsClarification(question=PRODUCT_QUESTION)


def test_a_free_slot_value_must_pass_the_actions_rule() -> None:
    """A whole sentence offered as a complaint ID is not an ID: the rule rejects it."""
    question = PendingQuestion(
        kind=QuestionKind.PROVIDE_SLOT, intent=Intent.COMPLAINT_STATUS, slot=SlotName.COMPLAINT_ID
    )
    llm = ScriptedLlm({"value": "no lo tengo a mano"})

    resolution = _clarifier(llm).interpret(
        _state(question), "no lo tengo a mano", NO_MATCH, SPANISH
    )

    assert resolution == NeedsClarification(question=question)


def test_a_reply_matching_the_pending_intent_is_read_as_an_answer() -> None:
    """ "La de ahorrar" sounds like a balance request; it answers the product question."""
    balance = MatchResult(
        kind=MatchKind.MATCHED, candidates=[MatchCandidate(intent=Intent.ACCOUNT_BALANCE, score=1)]
    )
    llm = ScriptedLlm({"choice": "savings_account"})

    resolution = _clarifier(llm).interpret(
        _state(PRODUCT_QUESTION), "la de ahorrar", balance, SPANISH
    )

    assert resolution.slots == {SlotName.PRODUCT_TYPE: ProductType.SAVINGS_ACCOUNT.value}


def test_a_reply_that_points_back_is_read_with_the_conversation() -> None:
    """ "La misma de antes" settles the product the customer named earlier in the case."""
    messages = InMemoryMessageStore()
    messages.append(stored_message(MessageSender.CUSTOMER, "ayer pagué con mi tarjeta de crédito"))
    messages.append(
        stored_message(MessageSender.AGENT, "¿Sobre qué producto? Responde con el número:")
    )
    llm = ScriptedLlm({"choice": "credit_card"})

    resolution = _clarifier(llm, messages).interpret(
        _state(PRODUCT_QUESTION), "la misma de antes", NO_MATCH, SPANISH
    )

    assert resolution == Resolved(
        intent=Intent.ACCOUNT_BALANCE,
        slots={SlotName.PRODUCT_TYPE: ProductType.CREDIT_CARD.value},
    )
    assert "Customer: ayer pagué con mi tarjeta de crédito" in llm.prompts[0]
