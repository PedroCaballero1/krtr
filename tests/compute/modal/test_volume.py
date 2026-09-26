"""Tests for the Modal volume adapter, using a fake `modal` module (the SDK is optional)."""

import sys
from enum import Enum
from pathlib import Path, PurePosixPath
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from krtr.compute.modal.volume import ModalStagingVolume


class FakeFileEntryType(Enum):
    """The two entry types of a volume listing that matter here."""

    FILE = 1
    DIRECTORY = 2


class FakeBatch:
    """Records the files put in a batched upload."""

    def __init__(self, puts: list[tuple[Path, PurePosixPath]]) -> None:
        """Appends every put to the shared `puts` list."""
        self._puts = puts

    def put_file(self, local_file: Path, remote_path: PurePosixPath) -> None:
        """Records one file put."""
        self._puts.append((local_file, remote_path))


class FakeUpload:
    """Context manager returned by `batch_upload`."""

    def __init__(self, puts: list[tuple[Path, PurePosixPath]]) -> None:
        """Keeps the shared `puts` list."""
        self._puts = puts

    def __enter__(self) -> FakeBatch:
        """Returns the batch that records puts."""
        return FakeBatch(self._puts)

    def __exit__(self, *exc_info: object) -> bool:
        """Never suppresses exceptions."""
        return False


class FakeVolumeHandle:
    """Stands in for `modal.Volume`, recording calls and serving a fixed listing."""

    def __init__(self) -> None:
        """Starts with no recorded calls and a listing of one file and one directory."""
        self.batch_force: bool | None = None
        self.puts: list[tuple[Path, PurePosixPath]] = []
        self.removed: list[tuple[str, bool]] = []
        self.entries = [
            SimpleNamespace(path="run-1", type=FakeFileEntryType.DIRECTORY),
            SimpleNamespace(
                path="run-1/parquet_path/products.parquet", type=FakeFileEntryType.FILE
            ),
        ]

    def batch_upload(self, force: bool = False) -> FakeUpload:
        """Records the `force` flag and returns the recording upload."""
        self.batch_force = force
        return FakeUpload(self.puts)

    def remove_file(self, path: str, recursive: bool = False) -> None:
        """Records the removal."""
        self.removed.append((path, recursive))

    def listdir(self, path: str, *, recursive: bool = False) -> list[Any]:
        """Serves the fixed listing."""
        return self.entries


@pytest.fixture
def volume_handle(monkeypatch: pytest.MonkeyPatch) -> FakeVolumeHandle:
    """Installs a fake `modal` package in `sys.modules` and returns its volume."""
    handle = FakeVolumeHandle()
    created: list[tuple[str, bool]] = []

    def from_name(name: str, *, create_if_missing: bool = False) -> FakeVolumeHandle:
        created.append((name, create_if_missing))
        return handle

    modal_module = ModuleType("modal")
    modal_module.Volume = SimpleNamespace(from_name=from_name)  # type: ignore[attr-defined]
    volume_module = ModuleType("modal.volume")
    volume_module.FileEntryType = FakeFileEntryType  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "modal", modal_module)
    monkeypatch.setitem(sys.modules, "modal.volume", volume_module)
    handle.created = created  # type: ignore[attr-defined]
    return handle


def test_the_volume_is_created_on_first_use(volume_handle: FakeVolumeHandle) -> None:
    """Staging must work on a fresh Modal account without creating the volume by hand."""
    ModalStagingVolume("krtr-staging")

    assert volume_handle.created == [("krtr-staging", True)]  # type: ignore[attr-defined]


def test_upload_overwrites_an_existing_file(volume_handle: FakeVolumeHandle) -> None:
    """Re-staging a run must replace the file instead of failing on the old copy."""
    volume = ModalStagingVolume("krtr-staging")
    local_path = Path("data/products.parquet")
    remote_path = PurePosixPath("run-1/parquet_path/products.parquet")

    volume.upload_file(local_path, remote_path)

    assert volume_handle.batch_force is True
    assert volume_handle.puts == [(local_path, remote_path)]


def test_remove_directory_removes_everything_under_it(volume_handle: FakeVolumeHandle) -> None:
    """Cleaning a run must delete its whole directory, not only the directory entry."""
    ModalStagingVolume("krtr-staging").remove_directory(PurePosixPath("run-1"))

    assert volume_handle.removed == [("run-1", True)]


def test_list_files_skips_directories(volume_handle: FakeVolumeHandle) -> None:
    """The listing must show staged files only, not the folders that contain them."""
    files = ModalStagingVolume("krtr-staging").list_files()

    assert files == [PurePosixPath("run-1/parquet_path/products.parquet")]
