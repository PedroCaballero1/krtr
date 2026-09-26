"""Loads the `.sql` files that hold this repository's SQL statements.

Exists so no SQL is embedded as a Python string literal: every table's DDL
and data-manipulation queries live in `.sql` files under
`krtr/database/queries/<table>/`, and this module is the single place that
reads them from disk. Consumed by any backend client that needs a table's
`table.sql` or `query.sql` (e.g. `krtr/database/neon/products/schema.py`).
"""

from pathlib import Path

QUERIES_DIRECTORY = Path(__file__).resolve().parent


def load_sql(directory: str, filename: str) -> str:
    """Reads a `.sql` file into a string.

    Exists so callers get SQL text by directory and file name instead of
    constructing paths themselves.

    Args:
        directory: Subdirectory under `krtr/database/queries/`, e.g.
            `products` (a table's queries) or `shared` (cross-table queries).
        filename: File name to read, e.g. `table.sql` or `query.sql`.

    Returns:
        str: the file's contents, unmodified.

    Raises:
        FileNotFoundError: if the `.sql` file does not exist.
    """
    return (QUERIES_DIRECTORY / directory / filename).read_text(encoding="utf-8")
