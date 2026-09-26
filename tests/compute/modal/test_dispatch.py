"""Tests for running a registered task inside the Modal container."""

import logging
from collections.abc import Iterator
from typing import Any

import pytest

from krtr.compute.modal import dispatch, registry
from krtr.compute.modal.config import RemoteTask
from krtr.compute.modal.dispatch import (
    REMOTE_LOG_FORMAT,
    configure_remote_logging,
    run_registered_task,
)
from krtr.compute.modal.registry import TaskDefinition


@pytest.fixture
def restored_root_logger() -> Iterator[None]:
    """Restores the root logger's handlers and level after a test reconfigures them."""
    root_logger = logging.getLogger()
    handlers, level = list(root_logger.handlers), root_logger.level
    yield
    root_logger.handlers = handlers
    root_logger.setLevel(level)


def test_run_registered_task_calls_the_registered_function_with_the_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The container must run the very function registered, with the arguments as keywords."""
    calls: list[dict[str, Any]] = []

    def _function(**arguments: Any) -> str:
        calls.append(arguments)
        return "summary"

    monkeypatch.setitem(registry.TASK_REGISTRY, RemoteTask.NEON_LOAD, TaskDefinition(_function))

    result = run_registered_task(RemoteTask.NEON_LOAD, {"table_name": "products", "truncate": True})

    assert result == "summary"
    assert calls == [{"table_name": "products", "truncate": True}]


def test_run_registered_task_rejects_an_unregistered_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A task missing from the registry must fail by name, before any function runs."""
    monkeypatch.setattr(registry, "TASK_REGISTRY", {})

    with pytest.raises(ValueError, match="neon-load"):
        run_registered_task(RemoteTask.NEON_LOAD, {})


def test_run_registered_task_lets_the_functions_errors_reach_modal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failing task must raise, so Modal marks the run as failed instead of succeeded."""

    def _failing(**arguments: Any) -> None:
        raise RuntimeError("connection lost")

    monkeypatch.setitem(registry.TASK_REGISTRY, RemoteTask.NEON_LOAD, TaskDefinition(_failing))

    with pytest.raises(RuntimeError, match="connection lost"):
        run_registered_task(RemoteTask.NEON_LOAD, {})


def test_configure_remote_logging_makes_info_messages_visible(
    restored_root_logger: None,
) -> None:
    """Without it the vertical's INFO narrative would be missing from the run's logs."""
    logging.getLogger().setLevel(logging.WARNING)

    configure_remote_logging()

    root_logger = logging.getLogger()
    assert root_logger.level == logging.INFO
    assert [handler.formatter._fmt for handler in root_logger.handlers] == [REMOTE_LOG_FORMAT]


def test_remote_log_format_has_no_timestamp() -> None:
    """Modal stamps every output line itself, so a second timestamp would be noise."""
    assert "asctime" not in dispatch.REMOTE_LOG_FORMAT
