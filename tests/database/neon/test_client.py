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
        self.rowcount = connection.rowcount_result

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

    def fetchone(self) -> tuple | None:
        """Returns the first of the connection's canned result rows, or None."""
        rows = self.connection.fetchall_result
        return rows[0] if rows else None


class FakeConnection:
    """Stands in for a psycopg2 connection, recording what happens to it."""

    def __init__(self) -> None:
        """Initializes empty call records and a default empty result set."""
        self.executed: list[tuple[str, dict | None]] = []
        self.committed = 0
        self.closed = False
        self.fetchall_result: list[tuple] = []
        self.rowcount_result = 0

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

    inserted = client.insert_rows("INSERT INTO t (a) VALUES %s", [])

    assert inserted == 0
    assert recorded == []
    assert connection.committed == 0


def test_insert_rows_calls_execute_values_and_commits(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies a batch goes to execute_values as one page (one round trip) and is committed."""
    client, connection = make_client(monkeypatch)
    recorded = []
    monkeypatch.setattr(
        client_module,
        "execute_values",
        lambda cursor, stmt, rows, page_size: recorded.append((stmt, rows, page_size)),
    )

    client.insert_rows("INSERT INTO t (a) VALUES %s", [(1,), (2,)])

    assert recorded == [("INSERT INTO t (a) VALUES %s", [(1,), (2,)], 2)]
    assert connection.committed == 1


def test_insert_rows_reports_what_the_database_inserted(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies the count is the database's, so rows skipped by ON CONFLICT are not counted."""
    client, connection = make_client(monkeypatch)
    connection.rowcount_result = 1
    monkeypatch.setattr(client_module, "execute_values", lambda *args, **kwargs: None)

    inserted = client.insert_rows(
        "INSERT INTO t (a) VALUES %s ON CONFLICT DO NOTHING", [(1,), (2,)]
    )

    assert inserted == 1


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


class FakePool:
    """Stands in for a psycopg2 ThreadedConnectionPool, recording how it is used."""

    def __init__(self, minconn: int, maxconn: int, dsn: str) -> None:
        """Records the sizing/DSN it was constructed with and counts checkouts."""
        self.minconn = minconn
        self.maxconn = maxconn
        self.dsn = dsn
        self.connection = FakeConnection()
        self.getconn_calls = 0
        self.putconn_calls = 0
        self.closed_all = False

    def getconn(self) -> "FakeConnection":
        """Returns the single fake connection this pool wraps, and counts it."""
        self.getconn_calls += 1
        return self.connection

    def putconn(self, connection: "FakeConnection") -> None:
        """Counts the connection being returned to the pool."""
        self.putconn_calls += 1

    def closeall(self) -> None:
        """Marks the pool as fully closed."""
        self.closed_all = True


def make_pooled_client(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[NeonClient, FakeConnection, list[FakePool]]:
    """Builds a NeonClient whose pool is a FakePool, recording every pool created."""
    fake_connection = FakeConnection()
    monkeypatch.setattr(client_module.psycopg2, "connect", lambda *a, **k: fake_connection)
    created_pools: list[FakePool] = []

    def fake_pool_factory(minconn: int, maxconn: int, dsn: str) -> FakePool:
        pool = FakePool(minconn, maxconn, dsn)
        pool.connection = fake_connection  # Share it so assertions see what ran.
        created_pools.append(pool)
        return pool

    monkeypatch.setattr(client_module, "ThreadedConnectionPool", fake_pool_factory)
    client = NeonClient(
        NeonConfig(connection_string="postgresql://u:p@h/db", pool_min_size=1, pool_max_size=5)
    )
    return client, fake_connection, created_pools


def test_execute_params_uses_the_pool_and_commits(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies execute_params runs the statement with its params via a pooled connection."""
    client, connection, pools = make_pooled_client(monkeypatch)

    client.execute_params("UPDATE t SET a = %(a)s WHERE id = %(id)s", {"a": 1, "id": 2})

    assert connection.executed == [("UPDATE t SET a = %(a)s WHERE id = %(id)s", {"a": 1, "id": 2})]
    assert connection.committed == 1
    assert pools[0].getconn_calls == 1
    assert pools[0].putconn_calls == 1


def test_execute_params_returns_how_many_rows_the_statement_affected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Callers such as the session revocation need to know whether the UPDATE matched anything."""
    client, connection, _ = make_pooled_client(monkeypatch)
    connection.rowcount_result = 2

    affected_rows = client.execute_params(
        "UPDATE t SET revoked = true WHERE customer = %(c)s", {"c": "1"}
    )

    assert affected_rows == 2


def test_fetch_one_returns_the_first_row(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies fetch_one passes params through and returns fetchone()'s result."""
    client, connection, _ = make_pooled_client(monkeypatch)
    connection.fetchall_result = [("row-1",)]

    result = client.fetch_one("SELECT a FROM t WHERE id = %(id)s", {"id": 1})

    assert result == ("row-1",)
    assert connection.executed == [("SELECT a FROM t WHERE id = %(id)s", {"id": 1})]


def test_fetch_all_returns_every_row(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies fetch_all passes params through and returns every row."""
    client, connection, _ = make_pooled_client(monkeypatch)
    connection.fetchall_result = [("row-1",), ("row-2",)]

    result = client.fetch_all("SELECT a FROM t WHERE status = %(status)s", {"status": "open"})

    assert result == [("row-1",), ("row-2",)]


def test_pool_is_created_once_and_reused_across_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies a second parameterized call reuses the pool instead of opening a new one."""
    client, _, pools = make_pooled_client(monkeypatch)

    client.execute_params("UPDATE t SET a = 1")
    client.fetch_one("SELECT 1")
    client.fetch_all("SELECT 1")

    assert len(pools) == 1
    assert pools[0].minconn == 1
    assert pools[0].maxconn == 5
    assert pools[0].getconn_calls == 3
    assert pools[0].putconn_calls == 3


def test_creating_the_client_alone_never_opens_the_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies the single-connection loader path never pays for a pool it doesn't use."""
    client, _, pools = make_pooled_client(monkeypatch)

    client.execute("CREATE TABLE t (id INT)")

    assert pools == []


def test_close_closes_the_pool_only_if_it_was_opened(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies close() tears down the pool when opened, and doesn't error when it wasn't."""
    client, connection, pools = make_pooled_client(monkeypatch)

    client.close()
    assert connection.closed
    assert pools == []  # Never opened, so nothing to close.

    client2, connection2, pools2 = make_pooled_client(monkeypatch)
    client2.execute_params("UPDATE t SET a = 1")
    client2.close()
    assert connection2.closed
    assert pools2[0].closed_all
