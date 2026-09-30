"""Registers the tasks that can be dispatched to Modal.

Exists so the single remote function and the local runner both resolve a
`RemoteTask` to the same vertical function, its resources and the arguments
that are local files, from one table. Adding a remotely runnable command means
adding one entry here; nothing in the Modal app changes. Consumed by the
runner, the staging step and the remote entrypoint in `krtr/compute/modal/`.
"""

from dataclasses import dataclass, field
from typing import Any, Callable

from krtr.compute.modal.config import RemoteTask, TaskResources
from krtr.database.neon.loader import run_table_load


@dataclass(frozen=True)
class TaskDefinition:
    """What it takes to run one task locally or on Modal.

    Exists to keep a task's function, its resources and its local-file
    arguments together, so the runner can stage the files and the remote
    entrypoint can call the function without knowing anything task-specific.
    Consumed by the runner, the staging step and the remote entrypoint.

    Attributes:
        function: The vertical function the task runs, taking plain values only.
        resources: The compute resources the task gets on Modal.
        local_file_arguments: Names of the `function` parameters that hold a
            path on this machine. They are uploaded to the staging volume and
            rewritten to the volume path before a remote run.
    """

    function: Callable[..., Any]
    resources: TaskResources = field(default_factory=TaskResources)
    local_file_arguments: tuple[str, ...] = ()


TASK_REGISTRY: dict[RemoteTask, TaskDefinition] = {
    RemoteTask.NEON_LOAD: TaskDefinition(
        function=run_table_load,
        local_file_arguments=("parquet_path",),
    ),
}


def get_task_definition(task: RemoteTask) -> TaskDefinition:
    """Looks up the definition registered for a task.

    Exists so callers fail with a clear message, instead of a bare `KeyError`,
    if a task was added to `RemoteTask` without being registered.

    Args:
        task: The task to look up.

    Returns:
        TaskDefinition: the function, resources and local-file arguments of `task`.

    Raises:
        ValueError: if `task` has no registered definition.
    """
    definition = TASK_REGISTRY.get(task)
    if definition is None:
        raise ValueError(f"Task '{task.value}' is not registered in TASK_REGISTRY")
    return definition
