"""Tests the `krtr database s3` commands: argument wiring and error exits."""

from datetime import date
from pathlib import Path

import pytest
from typer.testing import CliRunner

from krtr.cli.database.s3 import handler
from krtr.cli.main import app
from krtr.database.s3.artifacts import DatasetSummary, DownloadResult

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

    def list_files(self, s3_path: str) -> list[str]:
        """Returns fixed file names, or raises the configured error."""
        if self.error:
            raise self.error
        self.calls.append(("list", s3_path, Path()))
        return ["a.txt", "sub/b.txt"]

    def save_file_list(self, s3_path: str, file_names: list[str], output_directory: Path) -> Path:
        """Records the save call and returns a fake output path."""
        self.calls.append(("save", s3_path, output_directory))
        return output_directory / "list.txt"

    def list_datasets(self, s3_path: str) -> list[DatasetSummary]:
        """Returns a partitioned dataset with gaps and a single-file dataset."""
        if self.error:
            raise self.error
        return [
            DatasetSummary(
                name="complaints",
                is_partitioned=True,
                file_count=4,
                first_date=date(2024, 1, 1),
                last_date=date(2024, 1, 7),
                missing_dates=[date(2024, 1, 3), date(2024, 1, 4), date(2024, 1, 6)],
            ),
            DatasetSummary(name="customers.csv", is_partitioned=False, file_count=1),
        ]

    def save_catalog(
        self, s3_path: str, datasets: list[DatasetSummary], output_directory: Path
    ) -> Path:
        """Records the concept names saved and the output directory."""
        self.calls.append(("catalog", ",".join(d.concept for d in datasets), output_directory))
        return output_directory / "catalog.txt"

    def download_dataset(
        self,
        dataset: str,
        local_path: Path,
        s3_path: str,
        start_date: date | None,
        end_date: date | None,
    ) -> DownloadResult:
        """Records the dataset and resolved date range, or raises the configured error."""
        if self.error:
            raise self.error
        self.calls.append(("dataset", f"{dataset} {start_date} {end_date}", local_path))
        return DownloadResult(downloaded_files=[local_path])

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


def test_list_files_prints_one_file_name_per_line() -> None:
    """Verifies each listed file is printed on its own line so output can be piped."""
    result = runner.invoke(app, ["database", "s3", "list-files", "s3://b/d"])

    assert result.exit_code == 0
    assert result.stdout.splitlines() == ["a.txt", "sub/b.txt"]
    assert RecordingClient.calls[0] == ("list", "s3://b/d", Path())


def test_list_files_saves_to_data_directory_by_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verifies the listing is saved into the data directory without any flag."""
    monkeypatch.setattr(handler, "DEFAULT_DATA_DIRECTORY", tmp_path)

    result = runner.invoke(app, ["database", "s3", "list-files", "s3://b/d"])

    assert result.exit_code == 0
    assert RecordingClient.calls[-1] == ("save", "s3://b/d", tmp_path)


def test_list_files_no_save_skips_writing() -> None:
    """Verifies --no-save prints the list but never saves it."""
    result = runner.invoke(app, ["database", "s3", "list-files", "s3://b/d", "--no-save"])

    assert result.exit_code == 0
    assert result.stdout.splitlines() == ["a.txt", "sub/b.txt"]
    assert [call[0] for call in RecordingClient.calls] == ["list"]


@pytest.mark.parametrize("command", ["download-file", "download-directory"])
def test_client_errors_exit_with_code_one(command: str) -> None:
    """Verifies failures become a clean exit code 1 instead of a traceback."""
    RecordingClient.error = ValueError("bad path")

    result = runner.invoke(app, ["database", "s3", command, "s3://b/x", "out"])

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)


def test_list_files_error_exits_with_code_one() -> None:
    """Verifies a listing failure becomes exit code 1 with nothing printed to stdout."""
    RecordingClient.error = ValueError("bad path")

    result = runner.invoke(app, ["database", "s3", "list-files", "s3://b/d"])

    assert result.exit_code == 1
    assert result.stdout == ""


def test_datasets_prints_coverage_and_compact_missing_ranges() -> None:
    """Verifies missing days are shown as compact ranges and single files are labelled."""
    result = runner.invoke(app, ["database", "s3", "datasets"])

    assert result.exit_code == 0
    assert result.stdout.splitlines() == [
        "complaints  2024-01-01..2024-01-07  4 files  "
        "missing 3 day(s): 2024-01-03..2024-01-04, 2024-01-06",
        "customers.csv  single file",
    ]


def test_generate_catalog_saves_concept_names_to_data_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verifies the catalog holds every dataset name and goes to the data directory."""
    monkeypatch.setattr(handler, "DEFAULT_DATA_DIRECTORY", tmp_path)

    result = runner.invoke(app, ["database", "s3", "generate-catalog"])

    assert result.exit_code == 0
    assert RecordingClient.calls == [("catalog", "complaints,customers", tmp_path)]


def test_download_dataset_month_option_becomes_first_and_last_day(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verifies --month expands to the whole month and downloads into the data directory."""
    monkeypatch.setattr(handler, "DEFAULT_DATA_DIRECTORY", tmp_path)

    result = runner.invoke(
        app, ["database", "s3", "download-dataset", "complaints", "--month", "2024-02"]
    )

    assert result.exit_code == 0
    assert RecordingClient.calls == [("dataset", "complaints 2024-02-01 2024-02-29", tmp_path)]


def test_download_dataset_start_end_and_year_options(tmp_path: Path) -> None:
    """Verifies --start/--end and --year each reach the client as the right range."""
    runner.invoke(
        app,
        ["database", "s3", "download-dataset", "c", "--start", "2024-01-05", "--output", "o"],
    )
    runner.invoke(app, ["database", "s3", "download-dataset", "c", "--year", "2025"])

    assert [call[1] for call in RecordingClient.calls] == [
        "c 2024-01-05 None",
        "c 2025-01-01 2025-12-31",
    ]
    assert RecordingClient.calls[0][2] == Path("o")


def test_download_dataset_rejects_conflicting_date_options() -> None:
    """Verifies mixing --year with --start exits with code 1 before any download."""
    result = runner.invoke(
        app,
        ["database", "s3", "download-dataset", "c", "--year", "2025", "--start", "2024-01-01"],
    )

    assert result.exit_code == 1
    assert RecordingClient.calls == []
