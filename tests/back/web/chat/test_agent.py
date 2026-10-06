"""Tests AgentChatResponder: the engine answers, and the audit carries metadata, never text."""

import re
from datetime import date
from decimal import Decimal

import pytest

from krtr.back.ia.deterministic.artifacts import (
    ComplaintRecord,
    ComplaintStatus,
    ProductBalance,
    ProductType,
)
from krtr.back.ia.deterministic.config import DeterministicConfig
from krtr.back.ia.deterministic.readers import InMemoryComplaintsReader, InMemoryProductsReader
from krtr.back.ia.engine.config import EngineConfig
from krtr.back.ia.engine.factory import build_engine
from krtr.back.ia.engine.store import InMemoryConversationStateStore
from krtr.back.ia.matching.hashing import HashingEmbedder
from krtr.back.ia.messages.artifacts import MessageSender
from krtr.back.ia.messages.store import InMemoryMessageStore
from krtr.back.security.oidc.artifacts import InterfaceLanguage
from krtr.back.web.chat.agent import COMPLAINT_ID_PATTERN, AgentChatResponder
from krtr.back.web.chat.responder import PLACEHOLDER_REPLIES

COMPLAINT_ID = "CMP-J7LT0TPC5YC33ULTQJZD"  # The format of the `complaints` table.


@pytest.fixture
def messages() -> InMemoryMessageStore:
    """Keeps the stored messages, to check the engine still writes them."""
    return InMemoryMessageStore()


@pytest.fixture
def responder(messages: InMemoryMessageStore) -> AgentChatResponder:
    """Builds the responder over one customer's savings account and complaint."""
    products = InMemoryProductsReader(
        {
            "C1": [
                ProductBalance(
                    product_number="4001220077810000",
                    product_type=ProductType.SAVINGS_ACCOUNT,
                    currency="COP",
                    current_balance=Decimal("1500.25"),
                )
            ]
        }
    )
    complaint = ComplaintRecord(
        complaint_id=COMPLAINT_ID,
        created_on=date(2026, 9, 1),
        category="Technical",
        status=ComplaintStatus.OPEN,
    )
    config = EngineConfig(
        deterministic=DeterministicConfig(complaint_id_pattern=COMPLAINT_ID_PATTERN)
    )
    engine = build_engine(
        HashingEmbedder(),
        products,
        InMemoryComplaintsReader({"C1": [complaint]}),
        InMemoryConversationStateStore(),
        messages,
        config,
    )
    return AgentChatResponder(engine)


def test_a_balance_question_gets_the_customers_balance(responder: AgentChatResponder) -> None:
    """The engine answers with the session customer's data, masked."""
    answer = responder.answer_text(
        "C1", "INC-1", "¿Cuál es el saldo de mi cuenta de ahorros?", InterfaceLanguage.SPANISH
    )

    assert "1,500.25 COP" in answer.reply
    assert "4001220077810000" not in answer.reply
    assert answer.audit["outcome"] == "resolved"
    assert answer.audit["intent"] == "account_balance"


def test_the_audit_never_carries_the_text(responder: AgentChatResponder) -> None:
    """Balances belong in `messages`, never in `events` (§3.6)."""
    answer = responder.answer_text(
        "C1", "INC-1", "¿Cuál es el saldo de mi cuenta de ahorros?", InterfaceLanguage.SPANISH
    )

    assert "1,500.25" not in str(answer.audit)
    assert set(answer.audit) == {
        "responder",
        "kind",
        "outcome",
        "language",
        "intent",
        "match_kind",
        "guard_flags",
        "total_ms",
        "steps_ms",
    }
    assert answer.audit["total_ms"] >= 0


def test_the_question_and_reply_are_stored_for_the_case(
    responder: AgentChatResponder, messages: InMemoryMessageStore
) -> None:
    """Resuming a case needs both sides of the conversation (G17)."""
    responder.answer_text("C1", "INC-1", "saldo de mi cuenta de ahorros", InterfaceLanguage.SPANISH)

    senders = [message.sender for message in messages.list_case("C1", "INC-1")]

    assert senders == [MessageSender.CUSTOMER, MessageSender.AGENT]


def test_a_real_complaint_id_is_found_in_any_case(responder: AgentChatResponder) -> None:
    """IDs like CMP-J7LT0TPC5YC33ULTQJZD, even typed in lowercase, reach the complaint."""
    answer = responder.answer_text(
        "C1",
        "INC-1",
        f"Quiero saber el estado de mi queja {COMPLAINT_ID.lower()}",
        InterfaceLanguage.SPANISH,
    )

    assert COMPLAINT_ID in answer.reply
    assert answer.audit["intent"] == "complaint_status"


def test_the_complaint_pattern_matches_only_the_real_format() -> None:
    """Short or malformed IDs must not be taken for a complaint ID."""
    pattern = re.compile(COMPLAINT_ID_PATTERN)

    assert pattern.search(f"mi queja {COMPLAINT_ID}.")
    assert not pattern.search("mi queja PQR-104233")
    assert not pattern.search("CMP-SHORT")


def test_a_voice_note_gets_the_placeholder(responder: AgentChatResponder) -> None:
    """Speech-to-text is out of scope: the engine only reads text."""
    answer = responder.answer_voice("C1", "INC-1", InterfaceLanguage.PORTUGUESE)

    assert answer.reply == PLACEHOLDER_REPLIES[InterfaceLanguage.PORTUGUESE]
    assert answer.audit["kind"] == "voice"
