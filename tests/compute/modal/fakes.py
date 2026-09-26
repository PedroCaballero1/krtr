"""Fakes shared by the Modal tests: a staging volume and an executor that record their calls."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Any

from krtr.compute.modal.artifacts import CallState, LaunchedCall
from krtr.compute.modal.config import RemoteTask, RunStatus, TaskResources

DASHBOARD_URL = "https://modal.com/apps/krtr/fc-1"


class FakeVolume:
    """Stands in for a staging volume, recording what was uploaded and removed."""

    def __init__(self, files: list[PurePosixPath] | None = None) -> None:
        """Starts with the given files already in the volume."""
        self.uploads: list[tuple[Path, PurePosixPath]] = []
        self.removed_directories: list[PurePosixPath] = []
        self._files = files or []

    def upload_file(self, local_path: Path, remote_path: PurePosixPath) -> None:
        """Records the upload instead of sending it anywhere."""
        self.uploads.append((local_path, remote_path))

    def remove_directory(self, remote_directory: PurePosixPath) -> None:
        """Records the removed directory."""
        self.removed_directories.append(remote_directory)

    def list_files(self) -> list[PurePosixPath]:
        """Returns the files the volume was created with."""
        return self._files


class FakeSession:
    """Stands in for a Modal session, with a configurable result or failure."""

    def __init__(
        self, result: Any, spawn_error: BaseException | None, wait_error: BaseException | None
    ):
        """Keeps what `wait` returns and what `spawn` or `wait` should raise."""
        self.spawned: list[tuple[RemoteTask, dict[str, Any], TaskResources]] = []
        self.waited: list[str] = []
        self._result = result
        self._spawn_error = spawn_error
        self._wait_error = wait_error

    def spawn(
        self, task: RemoteTask, arguments: dict[str, Any], resources: TaskResources
    ) -> LaunchedCall:
        """Records the launch, or raises the configured error."""
        if self._spawn_error:
            raise self._spawn_error
        self.spawned.append((task, arguments, resources))
        return LaunchedCall(call_id="fc-1", dashboard_url=DASHBOARD_URL)

    def wait(self, call_id: str) -> Any:
        """Records the wait, then returns the result or raises the configured error."""
        self.waited.append(call_id)
        if self._wait_error:
            raise self._wait_error
        return self._result


class FakeExecutor:
    """Stands in for the Modal executor, recording sessions, inspections and cancellations."""

    def __init__(self) -> None:
        """Starts with no recorded calls; configure the attributes before running."""
        self.result: Any = None
        self.spawn_error: BaseException | None = None
        self.wait_error: BaseException | None = None
        self.state = CallState(status=RunStatus.RUNNING, dashboard_url=DASHBOARD_URL)
        self.detach_flags: list[bool] = []
        self.session: FakeSession | None = None
        self.inspections: list[tuple[str, bool]] = []
        self.cancelled: list[str] = []

    @contextmanager
    def open_session(self, detach: bool) -> Iterator[FakeSession]:
        """Records the `detach` flag and yields a session built from the configuration."""
        self.detach_flags.append(detach)
        self.session = FakeSession(self.result, self.spawn_error, self.wait_error)
        yield self.session

    def inspect_call(self, call_id: str, wait: bool) -> CallState:
        """Records the inspection and returns the configured state."""
        self.inspections.append((call_id, wait))
        return self.state

    def cancel(self, call_id: str) -> None:
        """Records the cancellation."""
        self.cancelled.append(call_id)
