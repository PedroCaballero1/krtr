"""Tests validating and coercing raw rows against a table's column specs."""

from datetime import date, datetime
from decimal import Decimal

import pytest

from krtr.database.neon.artifacts import ColumnSpec
from krtr.database.neon.validation import RowValidationError, validate_row

PRODUCT_SPECS = [
    ColumnSpec(name="product_id", data_type="character varying", is_nullable=False),
    ColumnSpec(name="current_balance", data_type="numeric", is_nullable=False),
    ColumnSpec(name="credit_limit", data_type="numeric", is_nullable=True),
    ColumnSpec(name="opening_date", data_type="date", is_nullable=False),
    ColumnSpec(
        name="last_transaction_date", data_type="timestamp without time zone", is_nullable=True
    ),
    ColumnSpec(name="has_linked_app", data_type="boolean", is_nullable=False),
    ColumnSpec(name="days_past_due", data_type="integer", is_nullable=True),
]


def test_validate_row_coerces_every_supported_type_in_column_order() -> None:
    """Verifies a fully-populated row is coerced to the right Python types, in order."""
    row = {
        "product_id": "P1",
        "current_balance": "150.50",
        "credit_limit": "500.00",
        "opening_date": "2024-01-15",
        "last_transaction_date": "2024-02-01T10:30:00",
        "has_linked_app": "true",
        "days_past_due": "3",
    }

    result = validate_row(row, PRODUCT_SPECS)

    assert result == (
        "P1",
        Decimal("150.50"),
        Decimal("500.00"),
        date(2024, 1, 15),
        datetime(2024, 2, 1, 10, 30),
        True,
        3,
    )


def test_validate_row_allows_missing_nullable_columns() -> None:
    """Verifies absent optional values become None instead of failing."""
    row = {
        "product_id": "P1",
        "current_balance": "10.00",
        "opening_date": date(2024, 1, 1),
        "has_linked_app": False,
    }

    result = validate_row(row, PRODUCT_SPECS)

    assert result == ("P1", Decimal("10.00"), None, date(2024, 1, 1), None, False, None)


def test_validate_row_raises_for_a_missing_required_column() -> None:
    """Verifies a missing NOT NULL column fails with a message naming it."""
    row = {"current_balance": "10.00", "opening_date": "2024-01-01", "has_linked_app": True}

    with pytest.raises(RowValidationError, match="product_id"):
        validate_row(row, PRODUCT_SPECS)


def test_validate_row_raises_for_an_unparseable_decimal() -> None:
    """Verifies a non-numeric value for a numeric column fails with a clear message."""
    row = {
        "product_id": "P1",
        "current_balance": "not-a-number",
        "opening_date": "2024-01-01",
        "has_linked_app": True,
    }

    with pytest.raises(RowValidationError, match="current_balance"):
        validate_row(row, PRODUCT_SPECS)


def test_validate_row_raises_for_an_unparseable_date() -> None:
    """Verifies a malformed date value fails with a clear message."""
    row = {
        "product_id": "P1",
        "current_balance": "10.00",
        "opening_date": "not-a-date",
        "has_linked_app": True,
    }

    with pytest.raises(RowValidationError, match="opening_date"):
        validate_row(row, PRODUCT_SPECS)


def test_validate_row_raises_for_an_unparseable_boolean() -> None:
    """Verifies a value that isn't a recognized boolean fails with a clear message."""
    row = {
        "product_id": "P1",
        "current_balance": "10.00",
        "opening_date": "2024-01-01",
        "has_linked_app": "maybe",
    }

    with pytest.raises(RowValidationError, match="has_linked_app"):
        validate_row(row, PRODUCT_SPECS)


def test_validate_row_accepts_native_date_and_datetime_objects() -> None:
    """Verifies values already typed by pyarrow (date/datetime) pass through untouched."""
    row = {
        "product_id": "P1",
        "current_balance": Decimal("10.00"),
        "opening_date": datetime(2024, 1, 1, 8, 0),
        "last_transaction_date": date(2024, 3, 1),
        "has_linked_app": True,
    }

    result = validate_row(row, PRODUCT_SPECS)

    assert result[3] == date(2024, 1, 1)
    assert result[4] == datetime(2024, 3, 1, 0, 0)
