"""Adapts a Modal Volume to the operations staging needs.

Exists to keep the only code that touches the Modal SDK's volume API in one
small class. The SDK is imported when the class is built, never at module
level, so importing this module never requires Modal. Consumed by the runner
and the `staging` CLI commands.
"""

import logging
from pathlib import Path, PurePosixPath

logger = logging.getLogger(__name__)


class ModalStagingVolume:
    """A named Modal Volume that holds the files staged for remote runs.

    Exists so staging can upload, remove and list files through the
    `StagingVolume` interface while the SDK stays behind this class. The volume
    is created on Modal the first time it is used. Consumed by the runner and
    the `staging` CLI commands.
    """

    def __init__(self, volume_name: str) -> None:
        """Connects to the named volume, creating it if it does not exist.

        Args:
            volume_name: Name of the Modal Volume used for staging.
        """
        import modal

        self._volume = modal.Volume.from_name(volume_name, create_if_missing=True)

    def upload_file(self, local_path: Path, remote_path: PurePosixPath) -> None:
        """Uploads a local file, replacing any file already at the destination.

        Args:
            local_path: The file on this machine.
            remote_path: The destination path inside the volume.

        Returns:
            None.
        """
        with self._volume.batch_upload(force=True) as batch:
            batch.put_file(local_path, remote_path)

    def remove_directory(self, remote_directory: PurePosixPath) -> None:
        """Removes a directory and everything under it from the volume.

        Args:
            remote_directory: The directory path inside the volume.

        Returns:
            None.
        """
        self._volume.remove_file(remote_directory.as_posix(), recursive=True)

    def list_files(self) -> list[PurePosixPath]:
        """Lists every file in the volume, skipping directories.

        Returns:
            list[PurePosixPath]: the path of each file inside the volume.
        """
        from modal.volume import FileEntryType

        entries = self._volume.listdir("/", recursive=True)
        return [PurePosixPath(entry.path) for entry in entries if entry.type == FileEntryType.FILE]
