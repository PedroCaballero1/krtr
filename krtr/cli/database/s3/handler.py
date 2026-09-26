"""Defines the `krtr database s3` CLI commands.

Exists to expose `S3Client` listing and downloads to users while keeping the commands thin:
parse input, call the vertical, report the result. Consumed by
`krtr/cli/database/__init__.py`, which registers `s3_app` on the CLI.
"""

import logging
from pathlib import Path
from typing import Annotated

import typer
from botocore.exceptions import BotoCoreError, ClientError

from krtr.database.s3.artifacts import DownloadResult
from krtr.database.s3.client import S3Client

logger = logging.getLogger(__name__)

s3_app = typer.Typer(name="s3", help="List and download data from S3.", no_args_is_help=True)

S3PathArgument = Annotated[str, typer.Argument(help="Source path, e.g. s3://bucket/path.")]
LocalPathArgument = Annotated[Path, typer.Argument(help="Local path to save the download to.")]


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
) -> None:
    """Prints the names of all files under an S3 directory, one per line.

    Exists to let users inspect a directory's contents from the command line
    before downloading it.

    Args:
        s3_path: `s3://bucket/prefix` path of the directory.

    Returns:
        None.
    """
    try:
        file_names = S3Client().list_files(s3_path)
    except (ValueError, BotoCoreError, ClientError) as error:
        raise _exit_with_error(error) from error
    logger.info("Listed %d file(s) under %s", len(file_names), s3_path)
    for file_name in file_names:
        typer.echo(file_name)
