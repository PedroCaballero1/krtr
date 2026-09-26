"""Validates and coerces raw source rows against a table's live column schema.

Exists so a loader checks each row's required-ness and type (dates,
decimals, booleans, ...) before insertion, without redeclaring the table's
shape in Python: the shape is read once, live, from the target table itself
(defined in that table's `table.sql`) via `NeonClient.get_column_specs`.
Consumed by `krtr/database/neon/products/loader.py` and any future table
loader.
"""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from krtr.database.neon.artifacts import ColumnSpec

TRUE_STRINGS = {"true", "t", "1", "yes"}
FALSE_STRINGS = {"false", "f", "0", "no"}


class RowValidationError(Exception):
    """A single row's value could not be validated against its column spec.

    Exists so a loader can catch exactly one row's failure and continue
    with the rest of the batch instead of the whole batch failing on the
    database's own type error.
    """


def validate_row(row: dict[str, Any], column_specs: list[ColumnSpec]) -> tuple[Any, ...]:
    """Validates and coerces one raw row dict against a table's column specs.

    Args:
        row: Raw column name -> value mapping for one source row.
        column_specs: The target table's columns, in insertion order.

    Returns:
        tuple: coerced values, one per `column_specs` entry, in order.

    Raises:
        RowValidationError: if a value is missing for a non-nullable column,
            or cannot be coerced to its column's type.
    """
    return tuple(_coerce(spec, row.get(spec.name)) for spec in column_specs)


def _coerce(spec: ColumnSpec, raw_value: Any) -> Any:
    """Coerces one raw value to the type its column spec expects.

    Args:
        spec: The column's name, Postgres data type and nullability.
        raw_value: The value read from the source row, or None if absent.

    Returns:
        Any: the coerced value, or None for a nullable, absent column.

    Raises:
        RowValidationError: if the value is missing for a non-nullable
            column, or does not match its column's type.
    """
    if raw_value is None or raw_value == "":
        if not spec.is_nullable:
            raise RowValidationError(f"Column '{spec.name}' is required but missing")
        return None
    try:
        return _COERCERS.get(spec.data_type, lambda value: value)(raw_value)
    except (TypeError, ValueError, InvalidOperation) as error:
        raise RowValidationError(
            f"Column '{spec.name}' ({spec.data_type}) has invalid value {raw_value!r}: {error}"
        ) from error


def _coerce_boolean(raw_value: Any) -> bool:
    """Coerces a boolean-ish value (bool, or a common yes/no string) to bool."""
    if isinstance(raw_value, bool):
        return raw_value
    normalized = str(raw_value).strip().lower()
    if normalized in TRUE_STRINGS:
        return True
    if normalized in FALSE_STRINGS:
        return False
    raise ValueError(f"not a boolean: {raw_value!r}")


def _coerce_date(raw_value: Any) -> date:
    """Coerces a date, datetime or ISO-8601 string to a plain date."""
    if isinstance(raw_value, datetime):
        return raw_value.date()
    if isinstance(raw_value, date):
        return raw_value
    return date.fromisoformat(str(raw_value))


def _coerce_datetime(raw_value: Any) -> datetime:
    """Coerces a datetime, date or ISO-8601 string to a datetime."""
    if isinstance(raw_value, datetime):
        return raw_value
    if isinstance(raw_value, date):
        return datetime(raw_value.year, raw_value.month, raw_value.day)
    return datetime.fromisoformat(str(raw_value))


_COERCERS = {
    "character varying": str,
    "text": str,
    "numeric": Decimal,
    "integer": int,
    "smallint": int,
    "bigint": int,
    "boolean": _coerce_boolean,
    "date": _coerce_date,
    "timestamp without time zone": _coerce_datetime,
    "timestamp with time zone": _coerce_datetime,
}
