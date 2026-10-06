"""Tests confirming guard flags with the LLM, with the case's history as context."""

from krtr.back.ia.matching.labels import GuardLabel
from krtr.back.ia.messages.artifacts import MessageSender
from krtr.back.ia.messages.store import InMemoryMessageStore
from krtr.back.ia.reasoning.artifacts import ConversationState
from krtr.back.ia.reasoning.llm.config import HistoryConfig
from krtr.back.ia.reasoning.llm.guard import LlmGuardConfirmer
from krtr.back.ia.reasoning.llm.history import ConversationHistory
from krtr.back.security.oidc.artifacts import InterfaceLanguage
from tests.back.ia.fakes import CUSTOMER_ID
from tests.back.ia.reasoning.llm.fakes import (
    CountingMessageStore,
    ScriptedLlm,
    stored_message,
    tasks_with,
)

SPANISH = InterfaceLanguage.SPANISH
STATE = ConversationState(incident_id="INC-1", customer_id=CUSTOMER_ID)
BOTH = [GuardLabel.AGGRESSIVE, GuardLabel.OFF_TOPIC]


def _confirmer(llm: ScriptedLlm, store: InMemoryMessageStore) -> LlmGuardConfirmer:
    return LlmGuardConfirmer(tasks_with(llm), ConversationHistory(store, HistoryConfig()))


def test_the_first_confirmed_flag_is_returned_and_the_history_is_read_once() -> None:
    """Aggressive isn't confirmed, off-topic is: one read of the history serves both calls."""
    store = CountingMessageStore()
    llm = ScriptedLlm({"category": "banking"}, {"category": "off_topic"})

    confirmed = _confirmer(llm, store).confirm_first(STATE, BOTH, "¿y el fútbol?", SPANISH)

    assert confirmed == GuardLabel.OFF_TOPIC
    assert store.reads == 1
    assert len(llm.prompts) == 2


def test_no_flag_is_confirmed_when_the_llm_reads_the_message_as_banking() -> None:
    """An angry reply about the customer's banking problem never closes the case."""
    store = CountingMessageStore()
    store.append(
        stored_message(
            MessageSender.CUSTOMER, "me cobraron dos veces la cuota del préstamo", "INC-1"
        )
    )
    llm = ScriptedLlm({"category": "banking"})

    confirmed = _confirmer(llm, store).confirm_first(
        STATE, [GuardLabel.AGGRESSIVE], "son unos ladrones", SPANISH
    )

    assert confirmed is None
    assert "Customer: me cobraron dos veces la cuota del préstamo" in llm.prompts[0]
