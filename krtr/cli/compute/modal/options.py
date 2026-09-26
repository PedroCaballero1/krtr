"""Defines the `--remote` and `--detach` options any command can add to run on Modal.

Exists so gaining the ability to run on Modal costs a command two parameters
and one call, instead of each command redefining the flags and their rules.
Imports nothing from the Modal SDK, so a command that adds these options
still starts, and runs locally, without Modal installed. Consumed by every
CLI command that can run on Modal, such as `krtr database neon load`.
"""

from typing import Annotated

import typer

from krtr.compute.modal.config import ExecutionMode

RemoteOption = Annotated[
    bool, typer.Option("--remote", help="Run on Modal and wait for the result.")
]
DetachOption = Annotated[
    bool,
    typer.Option(
        "--detach",
        help="Run on Modal and return once it starts; follow it with `krtr compute modal`.",
    ),
]


def resolve_execution_mode(remote: bool, detach: bool) -> ExecutionMode:
    """Turns the `--remote` and `--detach` flags into one execution mode.

    Exists so every command applies the same rule: neither flag runs locally,
    and the two flags cannot be combined, since a run either waits or returns.

    Args:
        remote: Whether `--remote` was given.
        detach: Whether `--detach` was given.

    Returns:
        ExecutionMode: `DETACHED` for `--detach`, `REMOTE` for `--remote`, else `LOCAL`.

    Raises:
        typer.BadParameter: if both flags were given.
    """
    if remote and detach:
        raise typer.BadParameter("--remote and --detach cannot be used together")
    if detach:
        return ExecutionMode.DETACHED
    if remote:
        return ExecutionMode.REMOTE
    return ExecutionMode.LOCAL
