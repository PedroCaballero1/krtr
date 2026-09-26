"""Loads a table's Parquet source into its Neon table.

Exists to read the source file in bounded-memory batches, validate each row
against the target table's live schema, and insert valid rows in bulk,
without ever materializing the whole file in memory, for any table under
`krtr/database/queries/` - not just one hardcoded table. Consumed by the
`krtr database neon load` CLI command.
"""

import logging
from pathlib import Path

import pyarrow.parquet as pq
from tqdm import tqdm

from krtr.database.neon.artifacts import ColumnSpec, LoadSummary, ValidationFailure
from krtr.database.neon.client import NeonClient
from krtr.database.neon.validation import RowValidationError, validate_row
from krtr.database.queries import load_sql

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 5_000


def load_table(
    table_name: str,
    parquet_path: Path,
    client: NeonClient,
    batch_size: int = DEFAULT_BATCH_SIZE,
    strict: bool = False,
) -> LoadSummary:
    """Loads a Parquet file into a Neon table in bounded-memory batches.

    Exists as the single entry point tying reading, validation and insertion
    together. Row groups are streamed from disk via pyarrow's
    `ParquetFile.iter_batches` and converted straight to Python rows with
    `RecordBatch.to_pylist()`, so memory use stays flat regardless of file
    size and no intermediate DataFrame is built. Rows are validated against
    the table's live schema (read via `NeonClient.get_column_specs`), and
    inserted using that table's `query.sql`.

    Args:
        table_name: Name of the target table, matching the directory
            `krtr/database/queries/<table_name>/query.sql`.
        parquet_path: The Parquet file to load.
        client: An open NeonClient to insert rows through.
        batch_size: Rows read and inserted per round trip.
        strict: When True, raise on the first invalid row instead of skipping
            and logging it.

    Returns:
        LoadSummary: rows read, rows loaded and any validation failures.

    Raises:
        RowValidationError: if `strict` is True and a row is invalid.
        FileNotFoundError: if no `query.sql` exists for `table_name`.
    """
    column_specs = client.get_column_specs(table_name)
    insert_statement = load_sql(table_name, "query.sql")
    parquet_file = pq.ParquetFile(parquet_path)
    summary = LoadSummary(rows_read=0, rows_loaded=0)
    description = f"Loading {table_name}"
    with tqdm(total=parquet_file.metadata.num_rows, unit="rows", desc=description) as bar:
        for batch in parquet_file.iter_batches(batch_size=batch_size):
            rows = batch.to_pylist()
            valid_rows = _validate_batch(rows, column_specs, summary, strict)
            client.insert_rows(insert_statement, valid_rows)
            summary.rows_read += len(rows)
            summary.rows_loaded += len(valid_rows)
            bar.update(len(rows))
    logger.info(
        "Loaded %d/%d rows into %s (%d failed)",
        summary.rows_loaded,
        summary.rows_read,
        table_name,
        summary.rows_failed,
    )
    return summary


def _validate_batch(
    rows: list[dict], column_specs: list[ColumnSpec], summary: LoadSummary, strict: bool
) -> list[tuple]:
    """Validates one batch of raw rows, collecting failures instead of raising.

    Exists to keep `load_table` focused on the read/insert loop.

    Args:
        rows: Raw row dicts from the current Parquet batch.
        column_specs: The target table's columns, in insertion order.
        summary: The running LoadSummary; failures are appended to it.
        strict: When True, re-raise the first RowValidationError instead of
            recording it and continuing.

    Returns:
        list[tuple]: column-ordered, coerced tuples for every row that validated.

    Raises:
        RowValidationError: if `strict` is True and a row is invalid.
    """
    valid_rows = []
    for offset, row in enumerate(rows):
        row_number = summary.rows_read + offset + 1
        try:
            valid_rows.append(validate_row(row, column_specs))
        except RowValidationError as error:
            if strict:
                raise
            logger.warning("Skipping invalid row %d: %s", row_number, error)
            summary.failures.append(ValidationFailure(row_number=row_number, reason=str(error)))
    return valid_rows
