"""Tests applying a table's schema from its `table.sql`."""

import pytest

from krtr.database.neon.schema import create_table_schema


class RecordingClient:
    """Stands in for NeonClient, recording every statement it is asked to run."""

    def __init__(self) -> None:
        """Starts with no recorded statements."""
        self.executed: list[str] = []

    def execute(self, statement: str) -> None:
        """Records the statement instead of running it."""
        self.executed.append(statement)


def test_create_table_schema_runs_that_tables_table_sql() -> None:
    """Verifies the exact contents of products/table.sql are executed, once."""
    client = RecordingClient()

    create_table_schema(client, "products")

    assert len(client.executed) == 1
    assert "CREATE TABLE IF NOT EXISTS products" in client.executed[0]
    assert "REFERENCES customers (customer_id)" in client.executed[0]


def test_create_table_schema_raises_for_a_table_with_no_sql_file() -> None:
    """Verifies an unknown table fails clearly instead of running empty SQL."""
    client = RecordingClient()

    with pytest.raises(FileNotFoundError):
        create_table_schema(client, "does_not_exist")

    assert client.executed == []
