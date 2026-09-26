"""Tests the `krtr database neon` commands: argument wiring and error exits."""

from pathlib import Path
from typing import Any

import psycopg2
import pytest
from typer.testing import CliRunner

from krtr.cli.database.neon import handler
from krtr.cli.main import app
from krtr.compute.modal.artifacts import RunOutcome
from krtr.compute.modal.config import ExecutionMode, RemoteTask, RunStatus
from krtr.compute.modal.errors import RemoteExecutionError
from krtr.database.neon.artifacts import LoadSummary
from krtr.database.neon.loader import DEFAULT_BATCH_SIZE
from krtr.database.neon.validation import RowValidationError
from krtr.database.neon.artifacts import LoadSummary

runner = CliRunner()


class RecordingClient:
    """Stands in for NeonClient in `create-schema`, which still opens its own connection."""
    """Stands in for NeonClient, recording calls and optionally failing."""

    calls: list[tuple[str, ...]] = []
    error: Exception | None = None

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


def _record_load_calls(
    monkeypatch: pytest.MonkeyPatch, parquet_path: Path, status: RunStatus = RunStatus.SUCCEEDED
) -> list[tuple[object, ...]]:
    """Replaces source resolution, the runner and the launch report with recorders."""
    calls: list[tuple[object, ...]] = []

    def _resolve(table: str, source: Path, force_convert: bool) -> Path:
        calls.append(("resolve", table, source, force_convert))
        return parquet_path

    def _run(task: RemoteTask, arguments: dict[str, Any], mode: ExecutionMode) -> RunOutcome:
        calls.append(("run", task, arguments, mode))
        return RunOutcome(
            status=status,
            result=LoadSummary(rows_read=2, rows_loaded=2),
            run_id="run-1",
            call_id="fc-1",
        )

    def _report(outcome: RunOutcome) -> None:
        calls.append(("report", outcome.call_id))

    monkeypatch.setattr(handler, "resolve_table_source", _resolve)
    monkeypatch.setattr(handler, "run_task", _run)
    monkeypatch.setattr(handler, "report_launched", _report)
    return calls


def _load_arguments(parquet_path: Path, **overrides: object) -> dict[str, Any]:
    """The arguments `neon load` must hand to the `neon-load` task."""
    arguments = {
        "table_name": "products",
        "parquet_path": parquet_path,
        "truncate": False,
        "strict": False,
        "batch_size": DEFAULT_BATCH_SIZE,
    }
    return {**arguments, **overrides}


def test_load_runs_locally_with_the_default_options(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Without --remote or --detach the load must run locally, exactly as it always has."""
    parquet_path = tmp_path / "products.parquet"
    calls = _record_load_calls(monkeypatch, parquet_path)

    result = runner.invoke(app, ["database", "neon", "load", "products", "--source", str(tmp_path)])

    assert result.exit_code == 0
    assert calls == [
        ("resolve", "products", tmp_path, False),
        ("run", RemoteTask.NEON_LOAD, _load_arguments(parquet_path), ExecutionMode.LOCAL),
    ]


def test_load_passes_truncate_force_convert_strict_and_batch_size(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verifies every load option is forwarded to the function that consumes it."""
    parquet_path = tmp_path / "products.parquet"
    calls = _record_load_calls(monkeypatch, parquet_path)
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
        (
            "run",
            RemoteTask.NEON_LOAD,
            _load_arguments(parquet_path, truncate=True, strict=True, batch_size=10),
            ExecutionMode.LOCAL,
        ),
    ]


def test_load_remote_runs_on_modal_and_reports_the_result_not_a_launch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """--remote waits for the load, so there is no "started, follow it" report."""
    calls = _record_load_calls(monkeypatch, tmp_path / "products.parquet")

    result = runner.invoke(
        app, ["database", "neon", "load", "products", "--source", str(tmp_path), "--remote"]
    )

    assert result.exit_code == 0
    assert [call[0] for call in calls] == ["resolve", "run"]
    assert calls[1][3] is ExecutionMode.REMOTE


def test_load_detach_runs_on_modal_and_tells_the_user_how_to_follow_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """--detach returns before the load finishes, so the user must be told what to do next."""
    calls = _record_load_calls(monkeypatch, tmp_path / "products.parquet", RunStatus.RUNNING)

    result = runner.invoke(
        app, ["database", "neon", "load", "products", "--source", str(tmp_path), "--detach"]
    )

    assert result.exit_code == 0
    assert calls[1][3] is ExecutionMode.DETACHED
    assert calls[2] == ("report", "fc-1")


def test_load_rejects_remote_and_detach_together_before_touching_anything(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The two flags contradict each other; nothing must be resolved, uploaded or run."""
    calls = _record_load_calls(monkeypatch, tmp_path / "products.parquet")

    result = runner.invoke(
        app,
        ["database", "neon", "load", "products", "--source", str(tmp_path), "--remote", "--detach"],
    )

    assert result.exit_code == 2
    assert calls == []


@pytest.mark.parametrize(
    "error",
    [psycopg2.Error("connection lost"), RowValidationError("bad"), RemoteExecutionError("failed")],
)
def test_load_failure_exits_with_code_one(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, error: Exception
) -> None:
    """Verifies a database, validation or Modal failure becomes exit code 1."""

    def _raise(task: RemoteTask, arguments: dict[str, Any], mode: ExecutionMode) -> RunOutcome:
        raise error

    monkeypatch.setattr(handler, "resolve_table_source", lambda table, source, force: tmp_path)
    monkeypatch.setattr(handler, "run_task", _raise)

    result = runner.invoke(app, ["database", "neon", "load", "products", "--source", str(tmp_path)])

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
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
