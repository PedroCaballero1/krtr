"""Defines the `krtr compute modal` CLI commands.

Exists to operate Modal entirely from `krtr`: check the environment, sync the
secret, list the tasks that can run remotely, follow the runs launched with
`--detach`, and manage the files staged for them, all without the `modal`
command or the dashboard. Commands stay thin: parse input, call the vertical,
report the result. Consumed by `krtr/cli/compute/__init__.py`, which registers
`modal_app`.
"""

import logging
from typing import Annotated

import typer

from krtr.cli.compute.modal.reporting import (
    describe_outcome,
    describe_run,
    describe_task,
    format_check,
)
from krtr.compute.modal.config import ModalConfig
from krtr.compute.modal.doctor import run_doctor
from krtr.compute.modal.errors import RemoteExecutionError
from krtr.compute.modal.registry import TASK_REGISTRY
from krtr.compute.modal.runner import build_modal_runner
from krtr.compute.modal.runs import RunRegistry
from krtr.compute.modal.secrets import sync_secret

logger = logging.getLogger(__name__)

modal_app = typer.Typer(
    name="modal", help="Run commands on Modal and follow the runs.", no_args_is_help=True
)
secrets_app = typer.Typer(name="secrets", help="Manage the Modal secret.", no_args_is_help=True)
staging_app = typer.Typer(
    name="staging", help="Manage files staged for Modal runs.", no_args_is_help=True
)
modal_app.add_typer(secrets_app, name="secrets")
modal_app.add_typer(staging_app, name="staging")

HANDLED_ERRORS = (ValueError, FileNotFoundError, RemoteExecutionError)

CallIdArgument = Annotated[
    str, typer.Argument(help="Modal call id printed when the run was launched.")
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
    logger.error("Modal command failed: %s", error)
    return typer.Exit(code=1)


@modal_app.command(name="doctor")
def doctor() -> None:
    """Checks that the environment is ready to run tasks on Modal.

    Exists so a missing token, secret or database connection is found by one
    command that names every problem, instead of one at a time mid-run.

    Returns:
        None.
    """
    report = run_doctor(ModalConfig())
    for check in report.checks:
        typer.echo(format_check(check))
    if not report.passed:
        raise typer.Exit(code=1)


@modal_app.command(name="tasks")
def tasks() -> None:
    """Prints the tasks that can run on Modal, with their resources.

    Exists so users can see which commands accept `--remote` and `--detach`.

    Returns:
        None.
    """
    for task, definition in TASK_REGISTRY.items():
        typer.echo(describe_task(task, definition))


@secrets_app.command(name="sync")
def sync_secrets() -> None:
    """Copies the allowed variables from `.env` into the Modal secret.

    Exists so the container receives the Neon connection string without
    creating the secret by hand. Run it again after the value changes.

    Returns:
        None.
    """
    try:
        names = sync_secret(ModalConfig().secret_name)
    except HANDLED_ERRORS as error:
        raise _exit_with_error(error) from error
    logger.info("Synced %d variable(s): %s", len(names), ", ".join(names))


@modal_app.command(name="runs")
def runs() -> None:
    """Prints the runs launched from this machine, oldest first.

    Exists so a `--detach` run can be found again without copying its call id.

    Returns:
        None.
    """
    try:
        records = RunRegistry(ModalConfig().runs_file).list_runs()
    except HANDLED_ERRORS as error:
        raise _exit_with_error(error) from error
    if not records:
        logger.info("No runs have been launched yet")
    for record in records:
        typer.echo(describe_run(record))


@modal_app.command(name="status")
def status(call_id: CallIdArgument) -> None:
    """Prints where a run launched earlier stands.

    Args:
        call_id: Modal call id printed when the run was launched.

    Returns:
        None.
    """
    try:
        outcome = build_modal_runner().get_status(call_id)
    except HANDLED_ERRORS as error:
        raise _exit_with_error(error) from error
    typer.echo(describe_outcome(outcome))


@modal_app.command(name="result")
def result(call_id: CallIdArgument) -> None:
    """Waits for a run launched earlier and prints its result.

    Args:
        call_id: Modal call id printed when the run was launched.

    Returns:
        None.
    """
    try:
        outcome = build_modal_runner().get_result(call_id)
    except HANDLED_ERRORS as error:
        raise _exit_with_error(error) from error
    typer.echo(describe_outcome(outcome))
    if outcome.result:
        typer.echo(outcome.result.model_dump_json(indent=2))


@modal_app.command(name="cancel")
def cancel(call_id: CallIdArgument) -> None:
    """Cancels a run that is still going.

    Its staged files are kept, so it can be launched again without uploading them.

    Args:
        call_id: Modal call id printed when the run was launched.

    Returns:
        None.
    """
    try:
        outcome = build_modal_runner().cancel(call_id)
    except HANDLED_ERRORS as error:
        raise _exit_with_error(error) from error
    typer.echo(describe_outcome(outcome))


@staging_app.command(name="list")
def list_staging() -> None:
    """Prints the files held in the staging volume.

    Exists so users can see what failed or cancelled runs left behind.

    Returns:
        None.
    """
    try:
        staged_files = build_modal_runner().list_staging()
    except HANDLED_ERRORS as error:
        raise _exit_with_error(error) from error
    if not staged_files:
        logger.info("No files are staged")
    for staged_file in staged_files:
        typer.echo(str(staged_file))


@staging_app.command(name="clean")
def clean_staging(
    run_id: Annotated[
        str | None,
        typer.Argument(help="Run to clean; default is every finished run with staged files."),
    ] = None,
) -> None:
    """Removes staged files left behind by runs that are no longer going.

    Exists so a failed or cancelled run's files, kept for a retry, can be
    deleted once they are no longer needed. A run still going is never cleaned.

    Args:
        run_id: The run to clean, or None for every finished run with staged files.

    Returns:
        None.
    """
    try:
        cleaned = build_modal_runner().clean_staging(run_id)
    except HANDLED_ERRORS as error:
        raise _exit_with_error(error) from error
    logger.info("Removed the staged files of %d run(s)", len(cleaned))
