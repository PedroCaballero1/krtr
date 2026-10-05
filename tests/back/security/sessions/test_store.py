"""Tests SessionStore: the right SQL runs, and tokens reach the database only encrypted."""

import os
from datetime import timedelta
from typing import Any

from krtr.back.security.crypto.cipher import AesGcmCipher
from krtr.back.security.sessions.artifacts import SessionRecord
from krtr.back.security.sessions.store import SessionStore
from krtr.database.queries import load_sql
from tests.back.security.oidc.fakes import START
from tests.back.security.sessions.fakes import tokens_expiring_at

KEY = os.urandom(32)
RECORD = SessionRecord(
    session_id_hash="a" * 64,
    customer_id="12345678",
    tokens=tokens_expiring_at(START + timedelta(minutes=5)),
    created_at=START,
    last_activity_at=START,
    absolute_expires_at=START + timedelta(minutes=30),
)


class RecordingNeonClient:
    """Stands in for NeonClient: records statements, answers one row and a row count."""

    def __init__(self, row: tuple[Any, ...] | None = None, rowcount: int = 0) -> None:
        """Answers fetch_one with `row` and execute_params with `rowcount`."""
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.row = row
        self.rowcount = rowcount

    def execute_params(self, statement: str, params: dict[str, Any] | None = None) -> int:
        """Records the statement instead of writing."""
        self.calls.append((statement, params or {}))
        return self.rowcount

    def fetch_one(
        self, statement: str, params: dict[str, Any] | None = None
    ) -> tuple[Any, ...] | None:
        """Records the query and returns the canned row."""
        self.calls.append((statement, params or {}))
        return self.row


def test_insert_writes_the_hash_and_only_encrypted_tokens() -> None:
    """Neither the cookie nor any token may appear in clear in what reaches Neon."""
    client = RecordingNeonClient()

    SessionStore(client, AesGcmCipher(KEY)).insert(RECORD)
    statement, params = client.calls[0]

    assert statement == load_sql("app_sessions", "insert_one.sql")
    assert params["session_id_hash"] == RECORD.session_id_hash
    assert isinstance(params["tokens_ciphertext"], bytes)
    assert (
        b"access-0" not in params["tokens_ciphertext"]
        and b"refresh-0" not in params["tokens_ciphertext"]
    )


def test_a_stored_session_reads_back_with_its_tokens() -> None:
    """What insert encrypts, find decrypts: the session's tokens survive the round trip."""
    writer = RecordingNeonClient()
    SessionStore(writer, AesGcmCipher(KEY)).insert(RECORD)
    params = writer.calls[0][1]
    row = (
        params["session_id_hash"],
        params["customer_id"],
        memoryview(params["tokens_ciphertext"]),  # psycopg2 returns BYTEA as a memoryview.
        params["created_at"],
        params["last_activity_at"],
        params["absolute_expires_at"],
        None,
    )

    found = SessionStore(RecordingNeonClient(row=row), AesGcmCipher(KEY)).find(
        RECORD.session_id_hash
    )

    assert found == RECORD


def test_find_returns_none_for_an_unknown_hash() -> None:
    """An unknown cookie maps to no session, not to an error."""
    assert SessionStore(RecordingNeonClient(row=None), AesGcmCipher(KEY)).find("b" * 64) is None


def test_revoke_customer_reports_how_many_sessions_it_closed() -> None:
    """The count decides whether session_revoked_by_new_login is recorded."""
    client = RecordingNeonClient(rowcount=1)

    revoked = SessionStore(client, AesGcmCipher(KEY)).revoke_customer("12345678", START)

    assert revoked == 1
    assert client.calls[0] == (
        load_sql("app_sessions", "revoke_by_customer.sql"),
        {"customer_id": "12345678", "revoked_at": START},
    )


def test_refreshed_tokens_are_stored_encrypted() -> None:
    """A refresh must not leave the new tokens in clear either."""
    client = RecordingNeonClient()

    SessionStore(client, AesGcmCipher(KEY)).replace_tokens(
        "a" * 64, tokens_expiring_at(START, generation=7)
    )
    statement, params = client.calls[0]

    assert statement == load_sql("app_sessions", "update_tokens.sql")
    assert b"refresh-7" not in params["tokens_ciphertext"]
