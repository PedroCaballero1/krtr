"""Tests NeonClient against a fake in-memory psycopg2 connection."""

from typing import Any

import pytest

from krtr.database.neon import client as client_module
from krtr.database.neon.artifacts import ColumnSpec
from krtr.database.neon.client import NeonClient
from krtr.database.neon.config import NeonConfig


class FakeCursor:
    """Records executed statements and serves a canned `fetchall` result."""

    def __init__(self, connection: "FakeConnection") -> None:
        """Keeps a reference to the owning fake connection."""
        self.connection = connection

    def __enter__(self) -> "FakeCursor":
        """Returns itself, like a real psycopg2 cursor context manager."""
        return self

    def __exit__(self, *exc_info: Any) -> bool:
        """Does nothing on exit; never suppresses exceptions."""
        return False

    def execute(self, statement: str, params: dict | None = None) -> None:
        """Records the statement and its params instead of running it."""
        self.connection.executed.append((statement, params))

    def fetchall(self) -> list[tuple]:
        """Returns the connection's canned result rows."""
        return self.connection.fetchall_result


class FakeConnection:
    """Stands in for a psycopg2 connection, recording what happens to it."""

    def __init__(self) -> None:
        """Initializes empty call records and a default empty result set."""
        self.executed: list[tuple[str, dict | None]] = []
        self.committed = 0
        self.closed = False
        self.fetchall_result: list[tuple] = []

    def cursor(self) -> FakeCursor:
        """Returns a new FakeCursor bound to this connection."""
        return FakeCursor(self)

    def commit(self) -> None:
        """Counts a commit instead of persisting anything."""
        self.committed += 1

    def close(self) -> None:
        """Marks the connection as closed."""
        self.closed = True


def make_client(monkeypatch: pytest.MonkeyPatch) -> tuple[NeonClient, FakeConnection]:
    """Builds a NeonClient backed by a fresh FakeConnection."""
    fake_connection = FakeConnection()
    monkeypatch.setattr(client_module.psycopg2, "connect", lambda *a, **k: fake_connection)
    client = NeonClient(NeonConfig(connection_string="postgresql://u:p@h/db"))
    return client, fake_connection


def test_execute_runs_the_statement_and_commits(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies execute() sends the statement and commits it."""
    client, connection = make_client(monkeypatch)

    client.execute("CREATE TABLE t (id INT)")

    assert connection.executed == [("CREATE TABLE t (id INT)", None)]
    assert connection.committed == 1


def test_truncate_table_executes_truncate_statement(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies truncate_table names the exact table in the SQL it runs."""
    client, connection = make_client(monkeypatch)

    client.truncate_table("products")

    assert connection.executed == [("TRUNCATE TABLE products", None)]


def test_insert_rows_skips_the_database_call_when_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies an empty batch never reaches execute_values or commit."""
    client, connection = make_client(monkeypatch)
    recorded = []
    monkeypatch.setattr(client_module, "execute_values", lambda *a: recorded.append(a))

    client.insert_rows("INSERT INTO t (a) VALUES %s", [])

    assert recorded == []
    assert connection.committed == 0


def test_insert_rows_calls_execute_values_and_commits(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies a non-empty batch is passed to execute_values and committed."""
    client, connection = make_client(monkeypatch)
    recorded = []
    monkeypatch.setattr(
        client_module, "execute_values", lambda cursor, stmt, rows: recorded.append((stmt, rows))
    )

    client.insert_rows("INSERT INTO t (a) VALUES %s", [(1,), (2,)])

    assert recorded == [("INSERT INTO t (a) VALUES %s", [(1,), (2,)])]
    assert connection.committed == 1


def test_get_column_specs_maps_nullability_and_preserves_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifies columns come back in query order with is_nullable as a bool."""
    client, connection = make_client(monkeypatch)
    connection.fetchall_result = [
        ("product_id", "character varying", "NO"),
        ("credit_limit", "numeric", "YES"),
    ]

    specs = client.get_column_specs("products")

    assert specs == [
        ColumnSpec(name="product_id", data_type="character varying", is_nullable=False),
        ColumnSpec(name="credit_limit", data_type="numeric", is_nullable=True),
    ]
    assert connection.executed[0][1] == {"table_name": "products"}


def test_get_column_specs_raises_for_an_unknown_table(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies a table with no columns (i.e. it doesn't exist) raises ValueError."""
    client, connection = make_client(monkeypatch)
    connection.fetchall_result = []

    with pytest.raises(ValueError, match="has no columns"):
        client.get_column_specs("does_not_exist")


def test_context_manager_closes_the_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies `with NeonClient(...)` closes the connection on exit."""
    client, connection = make_client(monkeypatch)

    with client:
        assert not connection.closed

    assert connection.closed
