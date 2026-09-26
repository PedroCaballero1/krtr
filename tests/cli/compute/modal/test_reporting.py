"""Tests for how runs, tasks and checks are formatted for the terminal."""

import logging
from datetime import UTC, datetime

import pytest

from krtr.cli.compute.modal.reporting import (
    describe_outcome,
    describe_run,
    describe_task,
    format_check,
    report_launched,
)
from krtr.compute.modal.artifacts import DoctorCheck, RunOutcome, RunRecord
from krtr.compute.modal.config import DoctorCheckName, RemoteTask, RunStatus
from krtr.compute.modal.registry import get_task_definition


def test_a_passed_and_a_failed_check_are_visibly_different_and_carry_their_detail() -> None:
    """Scanning a doctor report must show at a glance which checks failed, and why."""
    passed = format_check(
        DoctorCheck(name=DoctorCheckName.NEON_CONNECTION, passed=True, detail="Connected")
    )
    failed = format_check(
        DoctorCheck(name=DoctorCheckName.MODAL_SECRET, passed=False, detail="not found")
    )

    assert passed.startswith("ok")
    assert failed.startswith("FAILED")
    assert "Neon connection: Connected" in passed
    assert "Modal secret: not found" in failed


def test_a_task_is_described_with_its_resources_and_the_files_it_uploads() -> None:
    """Users decide whether to run remotely from what the task needs and uploads."""
    line = describe_task(RemoteTask.NEON_LOAD, get_task_definition(RemoteTask.NEON_LOAD))

    assert line.startswith("neon-load")
    assert "retries=0" in line
    assert "uploads: parquet_path" in line


def test_a_run_is_described_by_its_ids_task_status_and_start_time() -> None:
    """The `runs` listing must give everything needed to pick a run to inspect."""
    record = RunRecord(
        run_id="run-1",
        call_id="fc-1",
        dashboard_url="https://modal.com/apps/krtr/fc-1",
        task=RemoteTask.NEON_LOAD,
        arguments={},
        created_at=datetime(2026, 9, 26, 14, 30, 5, tzinfo=UTC),
        status=RunStatus.FAILED,
    )

    assert describe_run(record) == "fc-1  run-1  neon-load  failed  2026-09-26 14:30:05"


def test_an_outcome_shows_the_error_and_link_only_when_there_are_some() -> None:
    """A running run has no error to show, and a failed one must show why."""
    running = RunOutcome(status=RunStatus.RUNNING, call_id="fc-1", dashboard_url="https://d/1")
    failed = RunOutcome(status=RunStatus.FAILED, call_id="fc-1", error="connection lost")

    assert describe_outcome(running) == "fc-1  running  https://d/1"
    assert describe_outcome(failed) == "fc-1  failed  error: connection lost"


def test_a_launched_run_tells_the_user_the_command_to_follow_it(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """--detach returns immediately, so the exact next command must be in the output."""
    outcome = RunOutcome(
        status=RunStatus.RUNNING,
        run_id="run-1",
        call_id="fc-1",
        dashboard_url="https://modal.com/apps/krtr/fc-1",
    )

    with caplog.at_level(logging.INFO):
        report_launched(outcome)

    assert "krtr compute modal status fc-1" in caplog.text
    assert "https://modal.com/apps/krtr/fc-1" in caplog.text
