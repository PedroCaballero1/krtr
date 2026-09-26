"""Tests reading `.sql` files from krtr/database/queries/."""

import pytest

from krtr.database.queries import load_sql


def test_load_sql_reads_the_products_table_ddl() -> None:
    """Verifies the products table.sql is read verbatim, not reformatted."""
    contents = load_sql("products", "table.sql")

    assert "CREATE TABLE IF NOT EXISTS products" in contents
    assert "product_id VARCHAR(20) PRIMARY KEY" in contents


def test_load_sql_reads_the_products_insert_query() -> None:
    """Verifies the products query.sql is read verbatim."""
    contents = load_sql("products", "query.sql")

    assert contents.strip().startswith("--")
    assert "INSERT INTO products" in contents


def test_products_insert_query_has_exactly_one_placeholder() -> None:
    """Verifies query.sql (comments included) has one %s, as execute_values requires."""
    contents = load_sql("products", "query.sql")

    assert contents.count("%s") == 1


def test_load_sql_raises_for_a_missing_file() -> None:
    """Verifies a missing .sql file fails clearly instead of returning empty text."""
    with pytest.raises(FileNotFoundError):
        load_sql("products", "does_not_exist.sql")
