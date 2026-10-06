"""Tests loading a case's earlier messages for the LLM: its own case only, newest kept."""

from datetime import UTC, datetime, timedelta

import pytest

from krtr.back.ia.messages.artifacts import ConversationMessage, MessageSender
from krtr.back.ia.messages.store import InMemoryMessageStore
from krtr.back.ia.reasoning.artifacts import ConversationState
from krtr.back.ia.reasoning.llm.config import HistoryConfig
from krtr.back.ia.reasoning.llm.history import ConversationHistory
from krtr.back.security.oidc.artifacts import InterfaceLanguage
from tests.back.ia.fakes import CUSTOMER_ID, OTHER_CUSTOMER_ID

STATE = ConversationState(incident_id="INC-1", customer_id=CUSTOMER_ID)
STARTED_AT = datetime(2026, 10, 6, tzinfo=UTC)


class RefusingMessageStore(InMemoryMessageStore):
    """Fails if the messages are read at all."""

    def list_case(self, customer_id: str, incident_id: str) -> list[ConversationMessage]:
        raise AssertionError("The history must not be read")


def _store_with(
    *texts: str, incident_id: str = "INC-1", customer_id: str = CUSTOMER_ID
) -> InMemoryMessageStore:
    store = InMemoryMessageStore()
    for index, text in enumerate(texts):
        store.append(
            ConversationMessage(
                incident_id=incident_id,
                customer_id=customer_id,
                sender=MessageSender.CUSTOMER if index % 2 == 0 else MessageSender.AGENT,
                content=text,
                language=InterfaceLanguage.SPANISH,
                sent_at=STARTED_AT + timedelta(seconds=index),
            )
        )
    return store


def test_the_transcript_keeps_the_cases_messages_oldest_first_with_their_senders() -> None:
    """Customer and agent alternate as they were stored."""
    history = ConversationHistory(
        _store_with("hola", "¿qué necesitas?", "mi saldo"), HistoryConfig()
    )

    entries = history.load(STATE).entries

    assert [(e.sender, e.content) for e in entries] == [
        (MessageSender.CUSTOMER, "hola"),
        (MessageSender.AGENT, "¿qué necesitas?"),
        (MessageSender.CUSTOMER, "mi saldo"),
    ]


def test_past_the_cap_only_the_newest_messages_are_kept() -> None:
    """The oldest messages are dropped first, so the prompt fits the LLM's time budget."""
    history = ConversationHistory(
        _store_with("m1", "m2", "m3", "m4", "m5"), HistoryConfig(messages_kept=2)
    )

    assert [e.content for e in history.load(STATE).entries] == ["m4", "m5"]


def test_another_case_or_another_customers_messages_are_never_included() -> None:
    """The transcript is the case's own: same incident and same customer."""
    store = _store_with("mine")
    for message in _store_with("other case", incident_id="INC-2").messages:
        store.append(message)
    for message in _store_with("other customer", customer_id=OTHER_CUSTOMER_ID).messages:
        store.append(message)

    entries = ConversationHistory(store, HistoryConfig()).load(STATE).entries

    assert [e.content for e in entries] == ["mine"]


@pytest.mark.parametrize(
    "config", [HistoryConfig(messages_kept=0), HistoryConfig(max_characters=0)]
)
def test_a_limit_of_zero_sends_no_history_and_reads_nothing(config: HistoryConfig) -> None:
    """History off: the store isn't even queried."""
    transcript = ConversationHistory(RefusingMessageStore(), config).load(STATE)

    assert transcript.entries == []


def test_a_long_message_is_shortened_and_marked() -> None:
    """One very long message can't fill the prompt: it is cut to its own limit."""
    config = HistoryConfig(message_max_characters=10)
    history = ConversationHistory(_store_with("corto", "x" * 50), config)

    assert [e.content for e in history.load(STATE).entries] == ["corto", "x" * 10 + " […]"]


def test_repeated_long_messages_spend_the_budget_and_push_the_oldest_out() -> None:
    """Past the total budget, older messages go; the boundary message keeps what fits."""
    config = HistoryConfig(message_max_characters=10, max_characters=25)
    store = _store_with("primer mensaje", "a" * 40, "b" * 40, "c" * 40)
    history = ConversationHistory(store, config)

    contents = [e.content for e in history.load(STATE).entries]

    assert contents == ["a" * 5 + " […]", "b" * 10 + " […]", "c" * 10 + " […]"]
    assert sum(len(c.removesuffix(" […]")) for c in contents) == 25
