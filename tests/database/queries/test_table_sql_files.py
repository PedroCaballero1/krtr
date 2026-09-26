"""Tests that every table's `query.sql` inserts columns in the order its `table.sql` defines."""

import re

import pytest

from krtr.database.queries import QUERIES_DIRECTORY, load_sql

TABLES = sorted(path.name for path in QUERIES_DIRECTORY.iterdir() if (path / "table.sql").is_file())
NON_COLUMN_LINE_START = ("--", "PRIMARY", "FOREIGN", "UNIQUE", "CONSTRAINT", "CREATE", ")")


def _table_columns(table_sql: str) -> list[str]:
    """Returns the column names of a `CREATE TABLE`, in the order they are defined."""
    lines = [line.strip() for line in table_sql.splitlines()]
    return [
        line.split()[0] for line in lines if line and not line.startswith(NON_COLUMN_LINE_START)
    ]


def _insert_columns(query_sql: str) -> list[str]:
    """Returns the column names listed in an `INSERT INTO t (...)` statement."""
    column_list = re.search(r"INSERT INTO \w+ \((.*?)\)\s*VALUES", query_sql, re.DOTALL)
    assert column_list, "query.sql has no `INSERT INTO table (...) VALUES` statement"
    return [name.strip() for name in column_list.group(1).split(",")]


def test_the_tables_under_test_include_the_ones_the_cli_loads() -> None:
    """Guards the discovery itself: an empty list would make every test below pass vacuously."""
    assert {"products", "daily_exchange_rates"} <= set(TABLES)


@pytest.mark.parametrize("table", TABLES)
def test_insert_columns_match_the_table_columns_in_order(table: str) -> None:
    """A different order would load each value into the wrong column, with no error raised."""
    table_columns = _table_columns(load_sql(table, "table.sql"))
    insert_columns = _insert_columns(load_sql(table, "query.sql"))

    assert insert_columns == table_columns


def test_daily_exchange_rates_columns_are_the_documented_ones() -> None:
    """The column list is the documented contract of the table; pin it, in order."""
    assert _table_columns(load_sql("daily_exchange_rates", "table.sql")) == [
        "date",
        "source_currency",
        "target_currency",
        "exchange_rate",
        "buy_rate",
        "sell_rate",
        "source",
    ]
