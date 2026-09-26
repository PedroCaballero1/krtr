"""Tests for the registry of tasks that can be dispatched to Modal."""

import inspect

import pytest

from krtr.compute.modal import registry
from krtr.compute.modal.config import RemoteTask
from krtr.compute.modal.registry import TASK_REGISTRY, get_task_definition
from krtr.database.neon.loader import run_table_load


@pytest.mark.parametrize("task", list(RemoteTask))
def test_every_remote_task_is_registered(task: RemoteTask) -> None:
    """A task in the enum without a definition would only fail once dispatched."""
    assert get_task_definition(task) is TASK_REGISTRY[task]


@pytest.mark.parametrize("task", list(RemoteTask))
def test_declared_local_file_arguments_are_real_parameters(task: RemoteTask) -> None:
    """A misspelled file argument would skip staging and fail inside the container."""
    definition = get_task_definition(task)
    parameters = inspect.signature(definition.function).parameters

    assert set(definition.local_file_arguments) <= set(parameters)


def test_neon_load_runs_the_shared_load_and_stages_its_parquet_file() -> None:
    """The remote load must be the very function the local command calls."""
    definition = get_task_definition(RemoteTask.NEON_LOAD)

    assert definition.function is run_table_load
    assert definition.local_file_arguments == ("parquet_path",)


def test_neon_load_is_never_retried_automatically() -> None:
    """A retried load could insert the same rows twice."""
    assert get_task_definition(RemoteTask.NEON_LOAD).resources.retries == 0


def test_unregistered_task_fails_with_a_clear_message(monkeypatch: pytest.MonkeyPatch) -> None:
    """Forgetting to register a task must name the task, not raise a bare KeyError."""
    monkeypatch.setattr(registry, "TASK_REGISTRY", {})

    with pytest.raises(ValueError, match="neon-load"):
        get_task_definition(RemoteTask.NEON_LOAD)
