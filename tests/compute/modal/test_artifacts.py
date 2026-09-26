"""Tests for the Modal execution artifacts."""

from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

import pytest
from pydantic import ValidationError

from krtr.compute.modal.artifacts import RunRecord, StagedFile
from krtr.compute.modal.config import RemoteTask, RunStatus


def _build_record(**overrides: object) -> RunRecord:
    """Builds a RunRecord for a staged `neon-load` run, with optional overrides."""
    fields = {
        "run_id": "run-1",
        "call_id": "fc-123",
        "task": RemoteTask.NEON_LOAD,
        "arguments": {"table": "products", "parquet_path": Path("data/products.parquet")},
        "staged_files": [
            StagedFile(
                local_path=Path("data/products.parquet"),
                remote_path=PurePosixPath("run-1/products.parquet"),
            )
        ],
        "status": RunStatus.RUNNING,
    }
    return RunRecord(**{**fields, **overrides})


def test_run_record_survives_a_jsonl_round_trip() -> None:
    """A record written to `runs.jsonl` must read back with every field intact."""
    original = _build_record(created_at=datetime(2026, 9, 26, 12, 0, tzinfo=UTC))

    restored = RunRecord.model_validate_json(original.model_dump_json())

    assert restored.run_id == "run-1"
    assert restored.call_id == "fc-123"
    assert restored.task is RemoteTask.NEON_LOAD
    assert restored.status is RunStatus.RUNNING
    assert restored.created_at == datetime(2026, 9, 26, 12, 0, tzinfo=UTC)
    assert restored.staged_files == original.staged_files


def test_run_record_stores_path_arguments_as_strings() -> None:
    """Arguments are written as JSON, so a Path comes back as its string form."""
    restored = RunRecord.model_validate_json(_build_record().model_dump_json())

    assert restored.arguments["parquet_path"] == str(Path("data/products.parquet"))


def test_staged_remote_path_stays_posix() -> None:
    """The volume path is always POSIX, whatever the local operating system is."""
    staged_file = StagedFile.model_validate_json(
        '{"local_path": "data/products.parquet", "remote_path": "run-1/products.parquet"}'
    )

    assert staged_file.remote_path == PurePosixPath("run-1/products.parquet")


def test_run_record_defaults_created_at_to_an_aware_utc_time() -> None:
    """Records made without a timestamp get a timezone-aware UTC one, never a naive time."""
    created_at = _build_record().created_at

    assert created_at.utcoffset() == UTC.utcoffset(None)


def test_run_record_rejects_a_task_outside_the_closed_set() -> None:
    """Only registered tasks may be recorded, so a typo cannot slip into the registry."""
    with pytest.raises(ValidationError):
        _build_record(task="drop-database")
