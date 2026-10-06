"""Tests the message stores: the right SQL, text encrypted for Neon, reads scoped by case."""

import os
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from krtr.back.ia.artifacts import TurnOutcome
from krtr.back.ia.messages.artifacts import ConversationMessage, MessageSender
from krtr.back.ia.messages.store import InMemoryMessageStore, NeonMessageStore
from krtr.back.security.crypto.cipher import AesGcmCipher
from krtr.back.security.crypto.config import CryptoEnvironmentVariable
from krtr.back.security.oidc.artifacts import InterfaceLanguage
from krtr.database.queries import load_sql
from tests.back.ia.fakes import CUSTOMER_ID, OTHER_CUSTOMER_ID

CIPHER = AesGcmCipher(os.urandom(32))
SENT_AT = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)
REPLY = ConversationMessage(
    incident_id="INC-1",
    customer_id=CUSTOMER_ID,
    sender=MessageSender.AGENT,
    content="Saldo de tarjeta de crédito: ****9921 812,300.00 COP",
    language=InterfaceLanguage.SPANISH,
    outcome=TurnOutcome.RESOLVED,
    sent_at=SENT_AT,
)


class RecordingNeonClient:
    """Stands in for NeonClient: records statements, answers canned rows and a row count."""

    def __init__(self, rows: list[tuple[Any, ...]] | None = None, rowcount: int = 0) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.rows = rows or []
        self.rowcount = rowcount

    def execute_params(self, statement: str, params: dict[str, Any] | None = None) -> int:
        self.calls.append((statement, params or {}))
        return self.rowcount

    def fetch_all(
        self, statement: str, params: dict[str, Any] | None = None
    ) -> list[tuple[Any, ...]]:
        self.calls.append((statement, params or {}))
        return self.rows


def test_append_writes_the_text_only_encrypted() -> None:
    """The balance in a reply must not reach Neon in clear."""
    client = RecordingNeonClient()

    NeonMessageStore(client, CIPHER).append(REPLY)
    statement, params = client.calls[0]

    assert statement == load_sql("messages", "insert_one.sql")
    assert b"812,300.00" not in params["content"]
    assert CIPHER.decrypt(params["content"]).decode() == REPLY.content
    assert (params["sender"], params["language"], params["outcome"]) == (
        "agent",
        "es",
        "resolved",
    )


def test_a_customer_message_is_written_without_outcome() -> None:
    """Only agent replies have an outcome."""
    client = RecordingNeonClient()
    message = REPLY.model_copy(update={"sender": MessageSender.CUSTOMER, "outcome": None})

    NeonMessageStore(client, CIPHER).append(message)

    assert client.calls[0][1]["outcome"] is None


def test_list_case_filters_by_incident_and_customer_and_decrypts() -> None:
    """Both IDs go to the query, and rows come back with their text readable."""
    message_id = uuid4()
    row = (
        message_id,
        "INC-1",
        CUSTOMER_ID,
        "agent",
        CIPHER.encrypt(REPLY.content.encode()),
        "es",
        "resolved",
        SENT_AT,
    )
    client = RecordingNeonClient(rows=[row])

    messages = NeonMessageStore(client, CIPHER).list_case(CUSTOMER_ID, "INC-1")

    statement, params = client.calls[0]
    assert statement == load_sql("messages", "select_by_case.sql")
    assert params == {"incident_id": "INC-1", "customer_id": CUSTOMER_ID}
    assert messages == [REPLY.model_copy(update={"message_id": message_id})]


def test_purge_runs_the_retention_query_and_reports_the_count() -> None:
    """The daily job learns how many expired messages were deleted."""
    client = RecordingNeonClient(rowcount=7)

    deleted = NeonMessageStore(client, CIPHER).purge_expired()

    assert deleted == 7
    assert client.calls[0][0] == load_sql("messages", "purge.sql")


def test_from_environment_requires_the_messages_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without its own key the store refuses to start, naming the variable."""
    monkeypatch.delenv(CryptoEnvironmentVariable.MESSAGES_KEY, raising=False)

    with pytest.raises(ValueError, match="KRTR_MESSAGES_KEY"):
        NeonMessageStore.from_environment()


def test_the_in_memory_store_scopes_reads_to_the_customer() -> None:
    """Knowing an incident ID is not enough to read its messages."""
    store = InMemoryMessageStore()
    store.append(REPLY)

    assert store.list_case(CUSTOMER_ID, "INC-1") == [REPLY]
    assert store.list_case(OTHER_CUSTOMER_ID, "INC-1") == []
