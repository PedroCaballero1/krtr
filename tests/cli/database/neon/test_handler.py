"""Tests the `krtr database neon` commands: argument wiring and error exits."""

from pathlib import Path

import psycopg2
import pytest
from typer.testing import CliRunner

from krtr.cli.database.neon import handler
from krtr.cli.main import app
from krtr.database.neon.artifacts import LoadSummary

runner = CliRunner()


class RecordingClient:
    """Stands in for NeonClient, recording calls and optionally failing."""

    calls: list[tuple[str, ...]] = []
    error: Exception | None = None

    def __enter__(self) -> "RecordingClient":
        """Returns itself, like the real NeonClient context manager."""
        return self

    def __exit__(self, *exc_info: object) -> bool:
        """Never suppresses exceptions."""
        return False

    def truncate_table(self, table_name: str) -> None:
        """Records the truncated table name."""
        self.calls.append(("truncate", table_name))


@pytest.fixture(autouse=True)
def recording_client(monkeypatch: pytest.MonkeyPatch) -> type[RecordingClient]:
    """Replaces NeonClient in the handler and resets recorded state."""
    RecordingClient.calls = []
    RecordingClient.error = None
    monkeypatch.setattr(handler, "NeonClient", RecordingClient)
    return RecordingClient


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


def test_load_resolves_source_and_loads_without_truncating_by_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verifies the default load resolves the source and skips truncation."""
    resolved = []
    monkeypatch.setattr(
        handler,
        "resolve_table_source",
        lambda table, source, force_convert: resolved.append((table, source, force_convert))
        or tmp_path / "products.parquet",
    )
    monkeypatch.setattr(
        handler,
        "load_table",
        lambda table, path, client, batch_size, strict: LoadSummary(rows_read=2, rows_loaded=2),
    )

    result = runner.invoke(app, ["database", "neon", "load", "products", "--source", str(tmp_path)])

    assert result.exit_code == 0
    assert resolved == [("products", tmp_path, False)]
    assert RecordingClient.calls == []


def test_load_truncates_before_loading_when_requested(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verifies --truncate reaches the client before the load happens."""
    monkeypatch.setattr(
        handler, "resolve_table_source", lambda table, source, force_convert: tmp_path
    )
    monkeypatch.setattr(
        handler,
        "load_table",
        lambda table, path, client, batch_size, strict: LoadSummary(rows_read=0, rows_loaded=0),
    )

    result = runner.invoke(
        app, ["database", "neon", "load", "products", "--source", str(tmp_path), "--truncate"]
    )

    assert result.exit_code == 0
    assert RecordingClient.calls == [("truncate", "products")]


def test_load_passes_force_convert_and_strict_and_batch_size(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verifies every load option is forwarded to its underlying function."""
    resolved = []
    loaded = []
    monkeypatch.setattr(
        handler,
        "resolve_table_source",
        lambda table, source, force_convert: resolved.append((table, source, force_convert))
        or tmp_path,
    )
    monkeypatch.setattr(
        handler,
        "load_table",
        lambda table, path, client, batch_size, strict: loaded.append((batch_size, strict))
        or LoadSummary(rows_read=0, rows_loaded=0),
    )

    result = runner.invoke(
        app,
        [
            "database",
            "neon",
            "load",
            "products",
            "--source",
            str(tmp_path),
            "--force-convert",
            "--strict",
            "--batch-size",
            "10",
        ],
    )

    assert result.exit_code == 0
    assert resolved == [("products", tmp_path, True)]
    assert loaded == [(10, True)]


def test_load_error_exits_with_code_one(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Verifies a load failure (e.g. missing source file) becomes exit code 1."""

    def _raise(table: str, source: Path, force_convert: bool) -> Path:
        raise FileNotFoundError("no products source found")

    monkeypatch.setattr(handler, "resolve_table_source", _raise)

    result = runner.invoke(app, ["database", "neon", "load", "products", "--source", str(tmp_path)])

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
