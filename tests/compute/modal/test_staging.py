"""Tests for staging a task's local files on a volume."""

from pathlib import Path, PurePosixPath
from typing import Any

import pytest

from krtr.compute.modal.config import STAGING_MOUNT_PATH
from krtr.compute.modal.registry import TaskDefinition
from krtr.compute.modal.staging import (
    list_staged_files,
    remove_run_staging,
    stage_task_files,
)


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


def _task(*local_file_arguments: str) -> TaskDefinition:
    """Builds a task definition declaring the given local-file arguments."""
    return TaskDefinition(function=lambda **_: None, local_file_arguments=local_file_arguments)


def _write(directory: Path, name: str) -> Path:
    """Writes a small file and returns its path."""
    path = directory / name
    path.write_bytes(b"data")
    return path


def test_stage_uploads_the_file_under_its_run_and_argument(tmp_path: Path) -> None:
    """Each file lands in `<run-id>/<argument>/<file name>` of the volume."""
    volume = FakeVolume()
    parquet = _write(tmp_path, "products.parquet")

    result = stage_task_files(volume, _task("parquet_path"), {"parquet_path": parquet}, "run-1")

    expected_remote = PurePosixPath("run-1/parquet_path/products.parquet")
    assert volume.uploads == [(parquet, expected_remote)]
    assert [(f.local_path, f.remote_path) for f in result.staged_files] == [
        (parquet, expected_remote)
    ]


def test_stage_rewrites_the_file_argument_to_its_path_in_the_container(tmp_path: Path) -> None:
    """The task must receive the mounted path, and every other argument unchanged."""
    parquet = _write(tmp_path, "products.parquet")
    arguments: dict[str, Any] = {
        "table_name": "products",
        "parquet_path": parquet,
        "truncate": True,
    }

    result = stage_task_files(FakeVolume(), _task("parquet_path"), arguments, "run-1")

    assert result.arguments == {
        "table_name": "products",
        "parquet_path": STAGING_MOUNT_PATH / "run-1/parquet_path/products.parquet",
        "truncate": True,
    }
    assert isinstance(result.arguments["parquet_path"], PurePosixPath)
    assert arguments["parquet_path"] == parquet


def test_stage_keeps_files_with_the_same_name_apart(tmp_path: Path) -> None:
    """Two arguments pointing at same-named files must not overwrite each other."""
    first = _write(tmp_path, "one.parquet")
    (tmp_path / "other").mkdir()
    second = _write(tmp_path / "other", "one.parquet")
    volume = FakeVolume()

    result = stage_task_files(
        volume, _task("left", "right"), {"left": first, "right": second}, "run-1"
    )

    assert len({file.remote_path for file in result.staged_files}) == 2


def test_stage_with_no_local_files_touches_nothing() -> None:
    """A task that reads no local file must not upload anything."""
    volume = FakeVolume()

    result = stage_task_files(volume, _task(), {"table_name": "products"}, "run-1")

    assert volume.uploads == []
    assert result.staged_files == []
    assert result.arguments == {"table_name": "products"}


def test_stage_fails_before_uploading_when_any_file_is_missing(tmp_path: Path) -> None:
    """One missing file must not leave the other, valid one half-uploaded."""
    existing = _write(tmp_path, "there.parquet")
    volume = FakeVolume()

    with pytest.raises(FileNotFoundError, match="right"):
        stage_task_files(
            volume,
            _task("left", "right"),
            {"left": existing, "right": tmp_path / "missing.parquet"},
            "run-1",
        )

    assert volume.uploads == []


def test_stage_rejects_a_directory_in_place_of_a_file(tmp_path: Path) -> None:
    """A directory cannot be uploaded as the file a task expects."""
    with pytest.raises(FileNotFoundError, match="parquet_path"):
        stage_task_files(FakeVolume(), _task("parquet_path"), {"parquet_path": tmp_path}, "run-1")


def test_stage_requires_every_declared_file_argument() -> None:
    """A declared file argument that was not given must be named in the error."""
    volume = FakeVolume()

    with pytest.raises(ValueError, match="parquet_path"):
        stage_task_files(volume, _task("parquet_path"), {"table_name": "products"}, "run-1")

    assert volume.uploads == []


def test_remove_run_staging_removes_only_that_runs_directory() -> None:
    """Cleaning one run must never touch another run's staged files."""
    volume = FakeVolume()

    remove_run_staging(volume, "run-1")

    assert volume.removed_directories == [PurePosixPath("run-1")]


def test_list_staged_files_returns_what_the_volume_holds() -> None:
    """Listing must report the volume's files so users can see what was left behind."""
    files = [PurePosixPath("run-1/parquet_path/products.parquet")]

    assert list_staged_files(FakeVolume(files)) == files
