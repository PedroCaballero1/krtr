"""Tests for the reusable `--remote` and `--detach` options."""

import pytest
import typer

from krtr.cli.compute.modal.options import resolve_execution_mode
from krtr.compute.modal.config import ExecutionMode


@pytest.mark.parametrize(
    ("remote", "detach", "expected"),
    [
        (False, False, ExecutionMode.LOCAL),
        (True, False, ExecutionMode.REMOTE),
        (False, True, ExecutionMode.DETACHED),
    ],
)
def test_the_flags_select_the_execution_mode(
    remote: bool, detach: bool, expected: ExecutionMode
) -> None:
    """No flag must keep the command local, so existing usage never starts using Modal."""
    assert resolve_execution_mode(remote, detach) is expected


def test_remote_and_detach_together_are_rejected() -> None:
    """A run either waits or returns; combining the flags has no meaning."""
    with pytest.raises(typer.BadParameter, match="cannot be used together"):
        resolve_execution_mode(remote=True, detach=True)
