"""Tests the `krtr database neon` commands: argument wiring and error exits."""

from pathlib import Path

import psycopg2
import pytest
from typer.testing import CliRunner

from krtr.cli.database.neon import handler
from krtr.cli.main import app
from krtr.database.neon.artifacts import LoadSummary
from krtr.database.neon.loader import DEFAULT_BATCH_SIZE
from krtr.database.neon.validation import RowValidationError

runner = CliRunner()


class RecordingClient:
    """Stands in for NeonClient in `create-schema`, which still opens its own connection."""

    def __enter__(self) -> "RecordingClient":
        """Returns itself, like the real NeonClient context manager."""
        return self

    def __exit__(self, *exc_info: object) -> bool:
        """Never suppresses exceptions."""
        return False


@pytest.fixture(autouse=True)
def recording_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replaces NeonClient in the handler so `create-schema` never opens a connection."""
    monkeypatch.setattr(handler, "NeonClient", RecordingClient)


def test_create_schema_calls_create_table_schema_with_the_given_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifies the table argument reaches create_table_schema unchanged."""
    recorded = []
    monkeypatch.setattr(
        handler, "create_table_schema", lambda client, table: recorded.append(table)
    )

    result = runner.invoke(app, ["database", "neon", "create-schema", "products"])

    assert result.exit_code == 0
    assert recorded == ["products"]


def test_create_schema_error_exits_with_code_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies a schema failure becomes a clean exit code 1 instead of a traceback."""

    def _raise(client: object, table: str) -> None:
        raise psycopg2.Error("undefined table")

    monkeypatch.setattr(handler, "create_table_schema", _raise)

    result = runner.invoke(app, ["database", "neon", "create-schema", "products"])

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)


def _record_load_calls(
    monkeypatch: pytest.MonkeyPatch, parquet_path: Path
) -> list[tuple[object, ...]]:
    """Replaces source resolution and the load with recorders, returning the shared call log."""
    calls: list[tuple[object, ...]] = []

    def _resolve(table: str, source: Path, force_convert: bool) -> Path:
        calls.append(("resolve", table, source, force_convert))
        return parquet_path

    def _load(
        table_name: str, path: Path, truncate: bool, strict: bool, batch_size: int
    ) -> LoadSummary:
        calls.append(("load", table_name, path, truncate, strict, batch_size))
        return LoadSummary(rows_read=2, rows_loaded=2)

    monkeypatch.setattr(handler, "resolve_table_source", _resolve)
    monkeypatch.setattr(handler, "run_table_load", _load)
    return calls


def test_load_loads_the_resolved_file_with_the_default_options(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verifies the default load hands the resolved file to the load without truncating."""
    parquet_path = tmp_path / "products.parquet"
    calls = _record_load_calls(monkeypatch, parquet_path)

    result = runner.invoke(app, ["database", "neon", "load", "products", "--source", str(tmp_path)])

    assert result.exit_code == 0
    assert calls == [
        ("resolve", "products", tmp_path, False),
        ("load", "products", parquet_path, False, False, DEFAULT_BATCH_SIZE),
    ]


def test_load_passes_truncate_force_convert_strict_and_batch_size(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verifies every load option is forwarded to the function that consumes it."""
    parquet_path = tmp_path / "products.parquet"
    calls = _record_load_calls(monkeypatch, parquet_path)

    result = runner.invoke(
        app,
        [
            "database",
            "neon",
            "load",
            "products",
            "--source",
            str(tmp_path),
            "--truncate",
            "--force-convert",
            "--strict",
            "--batch-size",
            "10",
        ],
    )

    assert result.exit_code == 0
    assert calls == [
        ("resolve", "products", tmp_path, True),
        ("load", "products", parquet_path, True, True, 10),
    ]


@pytest.mark.parametrize("error", [psycopg2.Error("connection lost"), RowValidationError("bad")])
def test_load_failure_exits_with_code_one(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, error: Exception
) -> None:
    """Verifies a database or validation failure during the load becomes exit code 1."""

    def _raise(
        table_name: str, path: Path, truncate: bool, strict: bool, batch_size: int
    ) -> LoadSummary:
        raise error

    monkeypatch.setattr(handler, "resolve_table_source", lambda table, source, force: tmp_path)
    monkeypatch.setattr(handler, "run_table_load", _raise)

    result = runner.invoke(app, ["database", "neon", "load", "products", "--source", str(tmp_path)])

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)


def test_load_error_exits_with_code_one(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Verifies a load failure (e.g. missing source file) becomes exit code 1."""

    def _raise(table: str, source: Path, force_convert: bool) -> Path:
        raise FileNotFoundError("no products source found")

    monkeypatch.setattr(handler, "resolve_table_source", _raise)

    result = runner.invoke(app, ["database", "neon", "load", "products", "--source", str(tmp_path)])

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
