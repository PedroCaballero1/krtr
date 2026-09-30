"""Defines the Modal app and the single remote function every task runs through.

Exists so any registered task runs on Modal without a Modal function of its
own: the image, secret and staging volume are declared once here, and
`execute_task` dispatches to the task's vertical function. Importing this
module requires the optional `modal` SDK, so it is imported only on the remote
path, never by a local command. Consumed by the runner in
`krtr/compute/modal/`; Modal also imports it inside the container.
"""

from typing import Any

import modal

from krtr.compute.modal.config import (
    CONTAINER_PYTHON_VERSION,
    IMAGE_SOURCE_IGNORE_PATTERNS,
    REPOSITORY_ROOT,
    STAGING_MOUNT_PATH,
    ForwardedSecretVariable,
    ModalConfig,
    RemoteTask,
    TaskResources,
)
from krtr.compute.modal.dispatch import configure_remote_logging, run_registered_task

CONFIG = ModalConfig()
DEFAULT_RESOURCES = TaskResources()

# Dependencies come from `uv.lock`, so the container matches the local environment; `krtr`
# itself is copied in afterwards because `uv_sync` does not install the project.
IMAGE = (
    modal.Image.debian_slim(python_version=CONTAINER_PYTHON_VERSION)
    .uv_sync(str(REPOSITORY_ROOT), frozen=True)
    .add_local_python_source("krtr", ignore=list(IMAGE_SOURCE_IGNORE_PATTERNS))
)

# `required_keys` makes a missing variable fail with a clear message before the task starts.
SECRET = modal.Secret.from_name(
    CONFIG.secret_name, required_keys=[variable.value for variable in ForwardedSecretVariable]
)
STAGING_VOLUME = modal.Volume.from_name(CONFIG.staging_volume_name, create_if_missing=True)

app = modal.App(CONFIG.app_name)


@app.function(
    image=IMAGE,
    secrets=[SECRET],
    volumes={STAGING_MOUNT_PATH.as_posix(): STAGING_VOLUME.read_only()},
    cpu=DEFAULT_RESOURCES.cpu,
    memory=DEFAULT_RESOURCES.memory_mebibytes,
    timeout=DEFAULT_RESOURCES.timeout_seconds,
    region=CONFIG.region,
    single_use_containers=True,  # A fresh container always mounts the newly staged files.
    include_source=False,  # The image already carries the whole `krtr` package.
)
def execute_task(task: RemoteTask, arguments: dict[str, Any]) -> Any:
    """Runs one registered task inside the Modal container.

    Exists as the only remote function: every task is dispatched through it,
    so adding a task never touches this module. Per-task resources are applied
    by the runner on each call.

    Args:
        task: The task to run.
        arguments: The keyword arguments for the task's function.

    Returns:
        Any: whatever the task's function returns, e.g. a `LoadSummary`.
    """
    configure_remote_logging()
    return run_registered_task(task, arguments)
