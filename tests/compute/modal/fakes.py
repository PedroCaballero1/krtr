"""Fakes shared by the Modal tests: a staging volume and an executor that record their calls."""

import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from types import ModuleType, SimpleNamespace
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


class FakeSecretHandle:
    """Stands in for a `modal.Secret` handle, recording hydration and updates."""

    def __init__(self, sdk: "FakeSecretSdk") -> None:
        """Keeps the SDK whose events and errors this handle reports to."""
        self._sdk = sdk

    def hydrate(self) -> None:
        """Records the hydration, or raises the configured error (e.g. a missing secret)."""
        self._sdk.events.append("hydrate")
        if self._sdk.hydrate_error:
            raise self._sdk.hydrate_error

    def update(self, values: dict[str, str]) -> None:
        """Records the values that overwrite the secret."""
        self._sdk.events.append("update")
        self._sdk.updated_values = values


class FakeSecretSdk:
    """Records how the Modal secret API is used, with configurable failures."""

    def __init__(self) -> None:
        """Starts with no recorded calls and no configured errors."""
        self.events: list[str] = []
        self.created: list[tuple[str, dict[str, str], bool]] = []
        self.updated_values: dict[str, str] = {}
        self.looked_up: list[tuple[str, list[str]]] = []
        self.list_error: Exception | None = None
        self.hydrate_error: Exception | None = None

    def create(self, name: str, values: dict[str, str], allow_existing: bool = False) -> None:
        """Records the creation request."""
        self.events.append("create")
        self.created.append((name, values, allow_existing))

    def list(self, max_objects: int | None = None) -> list[Any]:
        """Records the request, or raises the configured error (e.g. bad credentials)."""
        self.events.append("list")
        if self.list_error:
            raise self.list_error
        return []

    def from_name(self, name: str, required_keys: list[str] | None = None) -> FakeSecretHandle:
        """Records the lookup and returns a handle to the secret."""
        self.looked_up.append((name, required_keys or []))
        return FakeSecretHandle(self)


def install_fake_secret_sdk(monkeypatch: Any) -> FakeSecretSdk:
    """Installs a fake `modal` SDK exposing only the secret API, and returns its recorder."""
    sdk = FakeSecretSdk()
    modal_module = ModuleType("modal")
    modal_module.Secret = SimpleNamespace(
        objects=SimpleNamespace(create=sdk.create, list=sdk.list), from_name=sdk.from_name
    )
    monkeypatch.setitem(sys.modules, "modal", modal_module)
    return sdk
