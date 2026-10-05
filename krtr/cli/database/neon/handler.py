"""Defines the `krtr database neon` CLI commands.

Exists to expose schema creation and loading for any table under
`krtr/database/queries/` while keeping commands thin: parse input, call the
vertical, report the result. The table is a command argument, not a
hardcoded per-table command - adding a new table only requires committing
its `table.sql` (and, for loading, `query.sql`) under
`krtr/database/queries/<table>/`, no new CLI or Python code. Consumed by
`krtr/cli/database/__init__.py`, which registers `neon_app`.
"""

import logging
from pathlib import Path
from typing import Annotated

import psycopg2
import typer

from krtr.cli.compute.modal.options import DetachOption, RemoteOption, resolve_execution_mode
from krtr.cli.compute.modal.reporting import report_launched
from krtr.compute.modal.config import ExecutionMode, RemoteTask, RunStatus
from krtr.compute.modal.errors import RemoteExecutionError
from krtr.compute.modal.runner import run_task
from krtr.database.neon.artifacts import LoadSummary
from krtr.database.neon.client import NeonClient
from krtr.database.neon.loader import DEFAULT_BATCH_SIZE, merge_load_summaries
from krtr.database.neon.schema import create_table_schema
from krtr.database.neon.source import resolve_partitioned_sources, resolve_table_source
from krtr.database.neon.validation import RowValidationError

logger = logging.getLogger(__name__)

neon_app = typer.Typer(
    name="neon", help="Create schemas for, and load, Neon Postgres tables.", no_args_is_help=True
)

DEFAULT_SOURCE_DIRECTORY = Path("data")
HANDLED_ERRORS = (
    ValueError,
    FileNotFoundError,
    RowValidationError,
    psycopg2.Error,
    RemoteExecutionError,
)

TableArgument = Annotated[
    str, typer.Argument(help="Table name, matching krtr/database/queries/<table>/.")
]
SourceOption = Annotated[
    Path, typer.Option("--source", help="Directory holding <table>.parquet/.csv.")
]
BatchSizeOption = Annotated[
    int, typer.Option("--batch-size", help="Rows read and inserted per round trip.")
]


def _exit_with_error(error: Exception) -> typer.Exit:
    """Logs an error and builds the failing exit signal.

    Exists so user-facing failures end with a clear message and a non-zero
    exit code instead of a traceback.

    Args:
        error: The exception that stopped the command.

    Returns:
        typer.Exit: an exit with code 1, meant to be raised by the caller.
    """
    logger.error("Neon command failed: %s", error)
    return typer.Exit(code=1)


@neon_app.command(name="create-schema")
def create_schema(table: TableArgument) -> None:
    """Creates a table in Neon from its `table.sql`, if it does not exist.

    Args:
        table: Table name, matching `krtr/database/queries/<table>/table.sql`.

    Returns:
        None.
    """
    try:
        with NeonClient() as client:
            create_table_schema(client, table)
    except (ValueError, FileNotFoundError, psycopg2.Error) as error:
        raise _exit_with_error(error) from error


@neon_app.command(name="load")
def load(
    table: TableArgument,
    source: SourceOption = DEFAULT_SOURCE_DIRECTORY,
    truncate: Annotated[
        bool, typer.Option("--truncate", help="Truncate the table before loading.")
    ] = False,
    strict: Annotated[
        bool,
        typer.Option("--strict", help="Stop on the first invalid row instead of skipping it."),
    ] = False,
    force_convert: Annotated[
        bool,
        typer.Option("--force-convert", help="Reconvert <table>.csv to Parquet even if cached."),
    ] = False,
    batch_size: BatchSizeOption = DEFAULT_BATCH_SIZE,
    remote: RemoteOption = False,
    detach: DetachOption = False,
) -> None:
    """Loads a table's source file into Neon, using its `query.sql`.

    Exists as the command-line entry point for populating any table: it
    resolves the source (converting a CSV to Parquet if needed), optionally
    truncates the table, and loads rows in batches.

    Args:
        table: Table name, matching `krtr/database/queries/<table>/query.sql`.
        source: Directory holding `<table>.parquet` or `<table>.csv`.
        truncate: When True, truncate the table before loading, so retries
            don't duplicate rows.
        strict: When True, stop the load on the first invalid row.
        force_convert: When True, reconvert `<table>.csv` to Parquet even if
            a cached `<table>.parquet` already exists.
        batch_size: Rows read and inserted per round trip.
        remote: When True, upload the source file and load it from Modal, waiting for
            the result.
        detach: When True, do the same but return as soon as the run has started.

    Returns:
        None.

    Examples:
        Load data/products.parquet (or data/products.csv, converted and cached)::

            krtr database neon load products

        Restart a load from scratch, so a retry never duplicates rows::

            krtr database neon load products --truncate

        Read from another directory and force the CSV to be reconverted::

            krtr database neon load products --source /path/to/data --force-convert

        Stop at the first invalid row, with larger batches::

            krtr database neon load products --strict --batch-size 10000

        Load from Modal, waiting for the result, or return as soon as it starts::

            krtr database neon load products --remote
            krtr database neon load products --detach
    """
    mode = resolve_execution_mode(remote, detach)
    try:
        parquet_path = resolve_table_source(table, source, force_convert)
        arguments = {
            "table_name": table,
            "parquet_path": parquet_path,
            "truncate": truncate,
            "strict": strict,
            "batch_size": batch_size,
        }
        outcome = run_task(RemoteTask.NEON_LOAD, arguments, mode)
    except HANDLED_ERRORS as error:
        raise _exit_with_error(error) from error
    if outcome.status is RunStatus.RUNNING:
        report_launched(outcome)
        return
    summary = outcome.result
    logger.info(
        "Loaded %d/%d rows (%d failed)", summary.rows_loaded, summary.rows_read, summary.rows_failed
    )


@neon_app.command(name="load-dataset")
def load_dataset(
    table: TableArgument,
    source: SourceOption = DEFAULT_SOURCE_DIRECTORY,
    truncate: Annotated[
        bool, typer.Option("--truncate", help="Truncate the table before the first file.")
    ] = False,
    strict: Annotated[
        bool,
        typer.Option("--strict", help="Stop on the first invalid row instead of skipping it."),
    ] = False,
    force_convert: Annotated[
        bool,
        typer.Option(
            "--force-convert", help="Reconvert every <table>_*.csv to Parquet even if cached."
        ),
    ] = False,
    batch_size: BatchSizeOption = DEFAULT_BATCH_SIZE,
    remote: RemoteOption = False,
) -> None:
    """Loads every daily file of a partitioned dataset into Neon, one by one.

    Exists for datasets split into many daily files (e.g. `transactions`,
    1,097 files under `year=/month=/day=` folders), which `load` cannot
    handle since it looks for a single `<table>.parquet`/`.csv`. Each file is
    loaded through the same `neon-load` task `load` uses, in path order
    (which is date order), so a single-file table and a partitioned one share
    the exact same loading logic.

    Args:
        table: Table name, matching `krtr/database/queries/<table>/query.sql`
            and the dataset directory `<source>/<table>/`.
        source: Directory holding `<table>/`.
        truncate: When True, truncate the table before the first file, so a
            retry never duplicates rows. Later files never truncate.
        strict: When True, stop the whole load on the first invalid row.
        force_convert: When True, reconvert every partition's CSV to Parquet
            even if a cached `.parquet` already exists next to it.
        batch_size: Rows read and inserted per round trip, per file.
        remote: When True, load each file from Modal, waiting for its result.

    Returns:
        None.

    Examples:
        Load every data/transactions/year=*/month=*/day=*/transactions_*.csv file::

            krtr database neon load-dataset transactions

        Restart from scratch, so a retry never duplicates rows::

            krtr database neon load-dataset transactions --truncate

        Run every file's load on Modal instead of this machine::

            krtr database neon load-dataset transactions --remote
    """
    mode = ExecutionMode.REMOTE if remote else ExecutionMode.LOCAL
    try:
        parquet_paths = resolve_partitioned_sources(table, source, force_convert)
        summaries = _load_each_partition(table, parquet_paths, truncate, strict, batch_size, mode)
    except HANDLED_ERRORS as error:
        raise _exit_with_error(error) from error
    summary = merge_load_summaries(summaries)
    logger.info(
        "Loaded %d/%d rows across %d files into %s (%d failed)",
        summary.rows_loaded,
        summary.rows_read,
        len(parquet_paths),
        table,
        summary.rows_failed,
    )


def _load_each_partition(
    table: str,
    parquet_paths: list[Path],
    truncate: bool,
    strict: bool,
    batch_size: int,
    mode: ExecutionMode,
) -> list[LoadSummary]:
    """Loads every partition file in order, truncating only before the first.

    Exists to keep `load_dataset` focused on parsing input and reporting the
    result; this is the loop that dispatches one `neon-load` task per file.

    Args:
        table: Target table name.
        parquet_paths: The partition files to load, in load order.
        truncate: When True, truncate the table before the first file.
        strict: When True, stop on the first invalid row.
        batch_size: Rows read and inserted per round trip, per file.
        mode: Where each file's load runs (LOCAL or REMOTE).

    Returns:
        list[LoadSummary]: one summary per file, in load order.
    """
    summaries = []
    for index, parquet_path in enumerate(parquet_paths):
        arguments = {
            "table_name": table,
            "parquet_path": parquet_path,
            "truncate": truncate and index == 0,
            "strict": strict,
            "batch_size": batch_size,
        }
        outcome = run_task(RemoteTask.NEON_LOAD, arguments, mode)
        logger.info("Loaded file %d/%d: %s", index + 1, len(parquet_paths), parquet_path.name)
        summaries.append(outcome.result)
    return summaries
