"""Tests the `krtr database s3` commands: argument wiring and error exits."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from krtr.cli.database.s3 import handler
from krtr.cli.main import app
from krtr.database.s3.artifacts import DownloadResult

runner = CliRunner()


class RecordingClient:
    """Stands in for S3Client, recording calls and optionally failing."""

    calls: list[tuple[str, str, Path]] = []
    error: Exception | None = None

    def download_file(self, s3_path: str, local_path: Path) -> DownloadResult:
        """Records the call, or raises the configured error."""
        return self._record("file", s3_path, local_path)

    def download_directory(self, s3_path: str, local_path: Path) -> DownloadResult:
        """Records the call, or raises the configured error."""
        return self._record("directory", s3_path, local_path)

    def _record(self, kind: str, s3_path: str, local_path: Path) -> DownloadResult:
        """Stores the call arguments and returns a one-file result."""
        if self.error:
            raise self.error
        self.calls.append((kind, s3_path, local_path))
        return DownloadResult(downloaded_files=[local_path])


@pytest.fixture(autouse=True)
def recording_client(monkeypatch: pytest.MonkeyPatch) -> type[RecordingClient]:
    """Replaces S3Client in the handler and resets recorded state."""
    RecordingClient.calls = []
    RecordingClient.error = None
    monkeypatch.setattr(handler, "S3Client", RecordingClient)
    return RecordingClient


def test_download_file_passes_paths_to_client() -> None:
    """Verifies the file command forwards the S3 path and local path to download_file."""
    result = runner.invoke(app, ["database", "s3", "download-file", "s3://b/k.txt", "out.txt"])

    assert result.exit_code == 0
    assert RecordingClient.calls == [("file", "s3://b/k.txt", Path("out.txt"))]


def test_download_directory_passes_paths_to_client() -> None:
    """Verifies the directory command forwards to download_directory, not download_file."""
    result = runner.invoke(app, ["database", "s3", "download-directory", "s3://b/d", "out"])

    assert result.exit_code == 0
    assert RecordingClient.calls == [("directory", "s3://b/d", Path("out"))]


@pytest.mark.parametrize("command", ["download-file", "download-directory"])
def test_client_errors_exit_with_code_one(command: str) -> None:
    """Verifies failures become a clean exit code 1 instead of a traceback."""
    RecordingClient.error = ValueError("bad path")

    result = runner.invoke(app, ["database", "s3", command, "s3://b/x", "out"])

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
