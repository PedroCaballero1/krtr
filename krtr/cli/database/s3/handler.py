"""Defines the `krtr database s3` CLI commands.

Exists to expose `S3Client` listing and downloads to users while keeping the commands thin:
parse input, call the vertical, report the result. Consumed by
`krtr/cli/database/__init__.py`, which registers `s3_app` on the CLI.
"""

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Annotated

import typer
from botocore.exceptions import BotoCoreError, ClientError

from krtr.database.s3.artifacts import DatasetSummary, DownloadResult
from krtr.database.s3.client import S3Client
from krtr.database.s3.config import DEFAULT_DATA_DIRECTORY
from krtr.database.s3.datasets import resolve_date_range

logger = logging.getLogger(__name__)

s3_app = typer.Typer(name="s3", help="List and download data from S3.", no_args_is_help=True)

S3PathArgument = Annotated[str, typer.Argument(help="Source path, e.g. s3://bucket/path.")]
LocalPathArgument = Annotated[Path, typer.Argument(help="Local path to save the download to.")]
SourceOption = Annotated[
    str,
    typer.Option("--source", help="Directory holding the datasets; default is the bucket root."),
]
OutputOption = Annotated[
    Path | None, typer.Option("--output", help="Where to save; default is the repo's data/.")
]
DAY_FORMAT = "%Y-%m-%d"
MONTH_FORMAT = "%Y-%m"
HANDLED_ERRORS = (ValueError, FileNotFoundError, BotoCoreError, ClientError)


def _report(result: DownloadResult) -> None:
    """Logs how many files a download wrote.

    Exists so both commands report results identically.

    Args:
        result: The download outcome to report.

    Returns:
        None.
    """
    logger.info("Downloaded %d file(s)", len(result.downloaded_files))


def _exit_with_error(error: Exception) -> typer.Exit:
    """Logs an error and builds the failing exit signal.

    Exists so user-facing failures end with a clear message and a non-zero
    exit code instead of a traceback.

    Args:
        error: The exception that stopped the command.

    Returns:
        typer.Exit: an exit with code 1, meant to be raised by the caller.
    """
    logger.error("S3 command failed: %s", error)
    return typer.Exit(code=1)


@s3_app.command(name="download-file")
def download_file(s3_path: S3PathArgument, local_path: LocalPathArgument) -> None:
    """Downloads a single S3 object to a local file.

    Exists to fetch one specific file from the command line.

    Args:
        s3_path: Full `s3://bucket/key` path of the object.
        local_path: Local file path to write.

    Returns:
        None.
    """
    try:
        _report(S3Client().download_file(s3_path, local_path))
    except (ValueError, BotoCoreError, ClientError) as error:
        raise _exit_with_error(error) from error


@s3_app.command(name="download-directory")
def download_directory(s3_path: S3PathArgument, local_path: LocalPathArgument) -> None:
    """Downloads every object under an S3 prefix into a local directory.

    Exists to fetch a whole directory from the command line.

    Args:
        s3_path: `s3://bucket/prefix` path of the directory.
        local_path: Local directory to write into.

    Returns:
        None.
    """
    try:
        _report(S3Client().download_directory(s3_path, local_path))
    except (ValueError, FileNotFoundError, BotoCoreError, ClientError) as error:
        raise _exit_with_error(error) from error


@s3_app.command(name="list-files")
def list_files(
    s3_path: Annotated[str, typer.Argument(help="Directory path, e.g. s3://bucket/path.")],
    save: Annotated[
        bool, typer.Option("--save/--no-save", help="Also save the list as a .txt in data/.")
    ] = True,
) -> None:
    """Prints the names of all files under an S3 directory, one per line.

    Exists to let users inspect a directory's contents from the command line
    before downloading it, and to keep a copy of the listing in `data/`.

    Args:
        s3_path: `s3://bucket/prefix` path of the directory.
        save: When True (default), also writes the list to a `.txt` file in the
            repository's `data/` directory.

    Returns:
        None.
    """
    try:
        client = S3Client()
        file_names = client.list_files(s3_path)
        if save:
            client.save_file_list(s3_path, file_names, DEFAULT_DATA_DIRECTORY)
    except (ValueError, BotoCoreError, ClientError) as error:
        raise _exit_with_error(error) from error
    logger.info("Listed %d file(s) under %s", len(file_names), s3_path)
    for file_name in file_names:
        typer.echo(file_name)


def _as_date(value: datetime | None) -> date | None:
    """Converts a parsed CLI datetime option to a plain date.

    Exists because Typer parses date options as datetimes.

    Args:
        value: The parsed option value, or None if the option was not given.

    Returns:
        date | None: the date part, or None.
    """
    return value.date() if value else None


def _format_date_ranges(days: list[date]) -> str:
    """Formats sorted days as compact ranges, e.g. `2024-01-03..2024-01-05, 2024-02-01`.

    Exists so long runs of missing days stay readable in the terminal.

    Args:
        days: Sorted, unique days.

    Returns:
        str: comma-separated days and `first..last` ranges of consecutive days.
    """
    ranges: list[list[date]] = []
    for day in days:
        if ranges and (day - ranges[-1][1]).days == 1:
            ranges[-1][1] = day
        else:
            ranges.append([day, day])
    return ", ".join(
        first.isoformat() if first == last else f"{first.isoformat()}..{last.isoformat()}"
        for first, last in ranges
    )


def _describe(dataset: DatasetSummary) -> str:
    """Builds the one-line description of a dataset for the `datasets` command.

    Exists to keep presentation out of the command function.

    Args:
        dataset: The dataset to describe.

    Returns:
        str: name, coverage, file count and any missing days.
    """
    if not dataset.is_partitioned:
        return f"{dataset.name}  single file"
    line = f"{dataset.name}  {dataset.first_date}..{dataset.last_date}  {dataset.file_count} files"
    if not dataset.missing_dates:
        return line
    missing = _format_date_ranges(dataset.missing_dates)
    return f"{line}  missing {len(dataset.missing_dates)} day(s): {missing}"


@s3_app.command(name="datasets")
def datasets(source: SourceOption = "") -> None:
    """Prints every dataset available, with its dates and missing days.

    Exists so users can see what can be downloaded before choosing.

    Args:
        source: Directory holding the datasets; empty means the bucket root.

    Returns:
        None.
    """
    try:
        summaries = S3Client().list_datasets(source)
    except HANDLED_ERRORS as error:
        raise _exit_with_error(error) from error
    for summary in summaries:
        typer.echo(_describe(summary))


@s3_app.command(name="generate-catalog")
def generate_catalog(source: SourceOption = "", output: OutputOption = None) -> None:
    """Saves the distinct concepts and their formats to a `.txt` file.

    Exists to keep a local record of which concepts the bucket holds, one per line
    as `concept | format`, e.g. `complaints | directory` for the dated
    `complaints/year=2024/...` files and `customers | .csv` for `customers.csv`.

    Args:
        source: Directory holding the datasets; empty means the bucket root.
        output: Directory to save into; defaults to the repository's `data/`.

    Returns:
        None.
    """
    try:
        client = S3Client()
        summaries = client.list_datasets(source)
        client.save_catalog(source, summaries, output or DEFAULT_DATA_DIRECTORY)
    except HANDLED_ERRORS as error:
        raise _exit_with_error(error) from error


@s3_app.command(name="download-dataset")
def download_dataset(
    dataset: Annotated[str, typer.Argument(help="Dataset name, e.g. complaints.")],
    source: SourceOption = "",
    start: Annotated[datetime | None, typer.Option(formats=[DAY_FORMAT], help="YYYY-MM-DD")] = None,
    end: Annotated[datetime | None, typer.Option(formats=[DAY_FORMAT], help="YYYY-MM-DD")] = None,
    year: Annotated[int | None, typer.Option(help="Only this year, e.g. 2025.")] = None,
    month: Annotated[
        datetime | None, typer.Option(formats=[MONTH_FORMAT], help="Only this month, YYYY-MM.")
    ] = None,
    output: OutputOption = None,
) -> None:
    """Downloads one dataset, optionally limited to a date range.

    Exists so users fetch data by concept and days; the `year=/month=/day=`
    folders are preserved under the output directory.

    Args:
        dataset: Dataset name, e.g. `complaints` or `customers.csv`.
        source: Directory holding the datasets; empty means the bucket root.
        start: Inclusive first day.
        end: Inclusive last day.
        year: Limit to a whole calendar year (exclusive with start/end/month).
        month: Limit to one month (exclusive with start/end/year).
        output: Directory to save into; defaults to the repository's `data/`.

    Returns:
        None.
    """
    try:
        start_date, end_date = resolve_date_range(
            _as_date(start), _as_date(end), year, _as_date(month)
        )
        result = S3Client().download_dataset(
            dataset, output or DEFAULT_DATA_DIRECTORY, source, start_date, end_date
        )
    except HANDLED_ERRORS as error:
        raise _exit_with_error(error) from error
    _report(result)
