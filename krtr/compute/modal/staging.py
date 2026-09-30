"""Stages a task's local files on a volume so a Modal container can read them.

Exists because a container cannot see this machine's disk: before a remote
run, each local file the task needs is uploaded to a named volume and the
task's arguments are rewritten to the path where the volume is mounted. The
volume outlives the local process, so the file is still there when a
`--detach` run starts after the CLI has exited. Consumed by the runner and by
the `staging` CLI commands.
"""

import logging
from pathlib import Path, PurePosixPath
from typing import Any, Protocol

from krtr.compute.modal.artifacts import StagedFile, StagingResult
from krtr.compute.modal.config import STAGING_MOUNT_PATH
from krtr.compute.modal.registry import TaskDefinition

logger = logging.getLogger(__name__)


class StagingVolume(Protocol):
    """The operations staging needs from a volume.

    Exists so staging depends on three small operations instead of the Modal
    SDK, which lets it be tested without Modal and keeps `modal` out of the
    local path. Implemented by `ModalStagingVolume`; consumed by this module.
    """

    def upload_file(self, local_path: Path, remote_path: PurePosixPath) -> None:
        """Uploads a local file to a path inside the volume.

        Args:
            local_path: The file on this machine.
            remote_path: The destination path inside the volume.

        Returns:
            None.
        """

    def remove_directory(self, remote_directory: PurePosixPath) -> None:
        """Removes a directory and everything under it from the volume.

        Args:
            remote_directory: The directory path inside the volume.

        Returns:
            None.
        """

    def list_files(self) -> list[PurePosixPath]:
        """Lists every file in the volume.

        Returns:
            list[PurePosixPath]: the path of each file inside the volume.
        """


def stage_task_files(
    volume: StagingVolume,
    definition: TaskDefinition,
    arguments: dict[str, Any],
    run_id: str,
) -> StagingResult:
    """Uploads a task's local files and rewrites its arguments to point at them.

    Exists so a task written against local paths runs unchanged on Modal: each
    argument the task declares as a local file is replaced by the path where
    the volume is mounted in the container. Every file is checked before any
    upload, so a missing file never leaves a partial upload behind.

    Args:
        volume: The staging volume to upload to.
        definition: The task's definition, naming its local-file arguments.
        arguments: The task's arguments, with local paths.
        run_id: The run the files belong to; they are stored under its directory.

    Returns:
        StagingResult: the arguments to send to Modal and the files uploaded.

    Raises:
        ValueError: if a declared file argument is missing from `arguments`.
        FileNotFoundError: if a declared file argument is not an existing file.
    """
    local_files = _require_local_files(definition, arguments)
    remote_arguments = dict(arguments)
    staged_files = []
    for argument_name, local_path in local_files.items():
        staged_file = _stage_file(volume, local_path, run_id, argument_name)
        remote_arguments[argument_name] = STAGING_MOUNT_PATH / staged_file.remote_path
        staged_files.append(staged_file)
    return StagingResult(arguments=remote_arguments, staged_files=staged_files)


def remove_run_staging(volume: StagingVolume, run_id: str) -> None:
    """Removes every file staged for one run.

    Exists so staged data is deleted once a run has succeeded, or on demand
    for a run that failed and is no longer going to be retried.

    Args:
        volume: The staging volume.
        run_id: The run whose directory is removed.

    Returns:
        None.
    """
    volume.remove_directory(PurePosixPath(run_id))
    logger.info("Removed staged files of run %s", run_id)


def list_staged_files(volume: StagingVolume) -> list[PurePosixPath]:
    """Lists the files currently held in the staging volume.

    Exists so users can see what a failed run left behind before cleaning it.

    Args:
        volume: The staging volume.

    Returns:
        list[PurePosixPath]: the path of each staged file inside the volume.
    """
    return volume.list_files()


def _require_local_files(definition: TaskDefinition, arguments: dict[str, Any]) -> dict[str, Path]:
    """Collects and validates the local files a task's arguments point at.

    Exists so staging fails before uploading anything if a file is absent.

    Args:
        definition: The task's definition, naming its local-file arguments.
        arguments: The task's arguments, with local paths.

    Returns:
        dict[str, Path]: each declared file argument's name and its local path.

    Raises:
        ValueError: if a declared file argument is missing from `arguments`.
        FileNotFoundError: if a declared file argument is not an existing file.
    """
    local_files = {}
    for argument_name in definition.local_file_arguments:
        if argument_name not in arguments:
            raise ValueError(f"Task argument '{argument_name}' is required but was not given")
        local_path = Path(arguments[argument_name])
        if not local_path.is_file():
            raise FileNotFoundError(
                f"Local file for argument '{argument_name}' is not an existing file: {local_path}"
            )
        local_files[argument_name] = local_path
    return local_files


def _stage_file(
    volume: StagingVolume, local_path: Path, run_id: str, argument_name: str
) -> StagedFile:
    """Uploads one local file under its run's directory.

    Exists so each file lands in `<run-id>/<argument>/<file name>`, which keeps
    runs apart and stops two arguments with the same file name from colliding.

    Args:
        volume: The staging volume to upload to.
        local_path: The file on this machine.
        run_id: The run the file belongs to.
        argument_name: The task argument that holds the file's path.

    Returns:
        StagedFile: the local path and the path it was uploaded to.
    """
    remote_path = PurePosixPath(run_id) / argument_name / local_path.name
    logger.info("Staging %s to volume path %s", local_path, remote_path)
    volume.upload_file(local_path, remote_path)
    return StagedFile(local_path=local_path, remote_path=remote_path)
