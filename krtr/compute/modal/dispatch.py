"""Runs a registered task inside the Modal container.

Exists to hold everything the remote function does apart from being a Modal
function: set up logging and call the task's vertical function. Keeping it
free of the Modal SDK lets it be tested without Modal, and leaves the Modal
app definition as a thin wrapper around it. Consumed by
`krtr/compute/modal/app.py`.
"""

import logging
from typing import Any

from krtr.compute.modal.config import RemoteTask
from krtr.compute.modal.registry import get_task_definition

logger = logging.getLogger(__name__)

# No timestamp: Modal already stamps every line of a container's output.
REMOTE_LOG_FORMAT = "%(levelname)s %(name)s: %(message)s"


def configure_remote_logging() -> None:
    """Configures logging for the container process, at INFO level.

    Exists because the container is a separate process that never runs the
    CLI entrypoint, which is where logging is normally configured; without
    this, the vertical's step-by-step log messages would not appear in the
    run's logs.

    Returns:
        None.
    """
    logging.basicConfig(level=logging.INFO, format=REMOTE_LOG_FORMAT, force=True)


def run_registered_task(task: RemoteTask, arguments: dict[str, Any]) -> Any:
    """Runs the vertical function registered for a task with the given arguments.

    Exists so the remote function needs no task-specific code: it resolves the
    task in the registry and calls the very function the local command calls.

    Args:
        task: The task to run.
        arguments: The keyword arguments for the task's function, with any
            local file already rewritten to its path in the container.

    Returns:
        Any: whatever the task's function returns, e.g. a `LoadSummary`.

    Raises:
        ValueError: if `task` is not registered.
    """
    definition = get_task_definition(task)
    logger.info("Running task %s", task.value)
    return definition.function(**arguments)
