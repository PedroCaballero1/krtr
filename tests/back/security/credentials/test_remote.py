"""Tests the import on Modal: upload, run, and an always-emptied Volume (task 3.5).

Acceptance: the upload, the invocation, and the cleanup of the Volume even when the import
fails; and a warning that asks for --force while Keycloak is running.
"""

from pathlib import Path, PurePosixPath

import pytest

from krtr.back.security.credentials.remote import KeycloakIsServing, import_on_modal
from krtr.back.security.keycloak.artifacts import PartialImportResult


class FakeVolume:
    """Stands in for ModalStagingVolume, keeping uploaded paths in a set."""

    def __init__(self) -> None:
        """Starts empty."""
        self.files: set[PurePosixPath] = set()

    def upload_file(self, local_path: Path, remote_path: PurePosixPath) -> None:
        """Records the upload."""
        self.files.add(remote_path)

    def remove_directory(self, remote_directory: PurePosixPath) -> None:
        """Removes every file under the directory."""
        self.files = {path for path in self.files if remote_directory not in path.parents}

    def list_files(self) -> list[PurePosixPath]:
        """Lists the files."""
        return sorted(self.files)


class FakeTarget:
    """Stands in for the krtr-web app on Modal."""

    def __init__(self, auth_running: bool = False, failure: Exception | None = None) -> None:
        """Configures whether auth is running and whether the import fails."""
        self.auth_running = auth_running
        self.failure = failure
        self.files_seen: list[PurePosixPath] = []
        self.volume: FakeVolume | None = None

    def auth_is_running(self) -> bool:
        """Reports the configured state."""
        return self.auth_running

    def run_import(self) -> PartialImportResult:
        """Records what the Volume held when the import ran, then succeeds or fails."""
        self.files_seen = self.volume.list_files() if self.volume else []
        if self.failure:
            raise self.failure
        return PartialImportResult(added=2, skipped=0)


def files(tmp_path: Path) -> list[Path]:
    """Creates two users files."""
    paths = [tmp_path / "krtr-users-0.json", tmp_path / "krtr-users-1.json"]
    for path in paths:
        path.write_text("{}")
    return paths


def test_files_are_uploaded_imported_and_removed(tmp_path: Path) -> None:
    """auth_import sees every file, and no hash stays on Modal afterwards."""
    volume, target = FakeVolume(), FakeTarget()
    target.volume = volume

    result = import_on_modal(files(tmp_path), volume, target)

    assert target.files_seen == [
        PurePosixPath("/import/krtr-users-0.json"),
        PurePosixPath("/import/krtr-users-1.json"),
    ]
    assert volume.list_files() == []
    assert result.added == 2


def test_the_volume_is_emptied_even_when_the_import_fails(tmp_path: Path) -> None:
    """A failed import must not leave 150,000 password hashes on the Volume."""
    volume, target = FakeVolume(), FakeTarget(failure=RuntimeError("Keycloak did not start"))
    target.volume = volume

    with pytest.raises(RuntimeError):
        import_on_modal(files(tmp_path), volume, target)

    assert volume.list_files() == []


def test_a_running_keycloak_stops_the_import_unless_forced(tmp_path: Path) -> None:
    """D20: two Keycloaks with local caches must not share the database."""
    volume = FakeVolume()

    with pytest.raises(KeycloakIsServing, match="--force"):
        import_on_modal(files(tmp_path), volume, FakeTarget(auth_running=True))
    forced = import_on_modal(files(tmp_path), volume, FakeTarget(auth_running=True), force=True)

    assert forced.added == 2
