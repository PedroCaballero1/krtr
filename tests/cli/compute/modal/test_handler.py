"""Tests the `krtr compute modal` commands: wiring, output and error exits."""

from pathlib import Path, PurePosixPath

import pytest
from typer.testing import CliRunner

from krtr.cli.compute.modal import handler
from krtr.cli.main import app
from krtr.compute.modal.artifacts import CallState, DoctorCheck, DoctorReport, RunRecord
from krtr.compute.modal.config import DoctorCheckName, ModalConfig, RemoteTask, RunStatus
from krtr.compute.modal.errors import RemoteExecutionError
from krtr.compute.modal.runner import RemoteRunner
from krtr.compute.modal.runs import RunRegistry
from krtr.database.neon.artifacts import LoadSummary
from tests.compute.modal.fakes import DASHBOARD_URL, FakeExecutor, FakeVolume

runner = CliRunner()


@pytest.fixture
def run_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> RunRegistry:
    """A registry over a temporary file, which the commands are pointed at."""
    runs_file = tmp_path / ".krtr" / "runs.jsonl"
    monkeypatch.setattr(handler, "ModalConfig", lambda: ModalConfig(runs_file=runs_file))
    return RunRegistry(runs_file)


@pytest.fixture
def executor() -> FakeExecutor:
    """A fake Modal executor."""
    return FakeExecutor()


@pytest.fixture
def volume() -> FakeVolume:
    """A fake staging volume."""
    return FakeVolume([PurePosixPath("run-1/parquet_path/products.parquet")])


@pytest.fixture(autouse=True)
def modal_runner(
    monkeypatch: pytest.MonkeyPatch,
    run_registry: RunRegistry,
    executor: FakeExecutor,
    volume: FakeVolume,
) -> RemoteRunner:
    """Makes every command that needs Modal use a runner over the fakes."""
    fake_runner = RemoteRunner(executor, volume, run_registry)
    monkeypatch.setattr(handler, "build_modal_runner", lambda: fake_runner)
    return fake_runner


def _add_run(
    run_registry: RunRegistry, call_id: str = "fc-1", status: RunStatus = RunStatus.RUNNING
) -> None:
    """Records a run as `--detach` would have left it."""
    run_registry.add(
        RunRecord(
            run_id=f"run-{call_id}",
            call_id=call_id,
            dashboard_url=DASHBOARD_URL,
            task=RemoteTask.NEON_LOAD,
            arguments={},
            status=status,
        )
    )


def _invoke(*arguments: str) -> object:
    """Runs `krtr compute modal <arguments>`."""
    return runner.invoke(app, ["compute", "modal", *arguments])


# --- doctor and tasks ---------------------------------------------------------------------


def _report(*passed_flags: bool) -> DoctorReport:
    """A doctor report whose checks have the given outcomes, in order."""
    names = list(DoctorCheckName)
    return DoctorReport(
        checks=[
            DoctorCheck(name=names[index], passed=passed, detail=f"detail {index}")
            for index, passed in enumerate(passed_flags)
        ]
    )


def test_doctor_prints_every_check_and_succeeds_when_all_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A healthy environment must exit 0 with every check listed."""
    monkeypatch.setattr(handler, "run_doctor", lambda config: _report(True, True, True))

    result = _invoke("doctor")

    assert result.exit_code == 0
    assert result.stdout.count("ok") == 3


def test_doctor_exits_with_one_but_still_prints_every_check_when_one_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Scripts rely on the exit code, and users need the whole report to fix everything at once."""
    monkeypatch.setattr(handler, "run_doctor", lambda config: _report(True, False, True))

    result = _invoke("doctor")

    assert result.exit_code == 1
    assert "FAILED" in result.stdout
    assert result.stdout.count("detail") == 3


def test_tasks_lists_the_tasks_that_can_run_remotely() -> None:
    """Users find out which commands accept --remote from this listing."""
    result = _invoke("tasks")

    assert result.exit_code == 0
    assert "neon-load" in result.stdout
    assert "uploads: parquet_path" in result.stdout


# --- secrets ------------------------------------------------------------------------------


def test_secrets_sync_uses_the_configured_secret_name(
    monkeypatch: pytest.MonkeyPatch, run_registry: RunRegistry
) -> None:
    """The secret the tasks read must be the one that is synced."""
    synced: list[str] = []
    monkeypatch.setattr(handler, "ModalConfig", lambda: ModalConfig(secret_name="custom-secret"))
    monkeypatch.setattr(
        handler, "sync_secret", lambda name: synced.append(name) or ["NEON_DB_HOST"]
    )

    result = _invoke("secrets", "sync")

    assert result.exit_code == 0
    assert synced == ["custom-secret"]


@pytest.mark.parametrize("error", [ValueError("Missing NEON_DB_HOST"), RemoteExecutionError("x")])
def test_secrets_sync_failure_exits_with_code_one(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    """A missing variable or SDK must end with a message and code 1, not a traceback."""

    def _raise(name: str) -> list[str]:
        raise error

    monkeypatch.setattr(handler, "sync_secret", _raise)

    result = _invoke("secrets", "sync")

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)


# --- runs, status, result, cancel -----------------------------------------------------------


def test_runs_lists_recorded_runs_oldest_first(run_registry: RunRegistry) -> None:
    """The listing is how a detached run is found again."""
    _add_run(run_registry, "fc-1", RunStatus.SUCCEEDED)
    _add_run(run_registry, "fc-2", RunStatus.RUNNING)

    lines = _invoke("runs").stdout.strip().splitlines()

    assert [line.split()[0] for line in lines] == ["fc-1", "fc-2"]
    assert "succeeded" in lines[0]
    assert "running" in lines[1]


def test_runs_with_nothing_recorded_succeeds_with_no_listing() -> None:
    """A fresh checkout has no runs, which is not an error."""
    result = _invoke("runs")

    assert result.exit_code == 0
    assert result.stdout.strip() == ""


def test_status_prints_the_state_of_a_run(run_registry: RunRegistry) -> None:
    """`status` must show the call id, its state and the dashboard link."""
    _add_run(run_registry)

    result = _invoke("status", "fc-1")

    assert result.exit_code == 0
    assert result.stdout.strip() == f"fc-1  running  {DASHBOARD_URL}"


def test_status_of_an_unknown_call_id_exits_with_code_one() -> None:
    """A mistyped id must fail cleanly and say which id was not found."""
    result = _invoke("status", "fc-999")

    assert result.exit_code == 1


def test_result_prints_the_tasks_result_as_json(
    run_registry: RunRegistry, executor: FakeExecutor
) -> None:
    """The load summary is what the user wants from a finished detached run."""
    _add_run(run_registry)
    executor.state = CallState(
        status=RunStatus.SUCCEEDED,
        dashboard_url=DASHBOARD_URL,
        result=LoadSummary(rows_read=5, rows_loaded=4),
    )

    result = _invoke("result", "fc-1")

    assert result.exit_code == 0
    assert '"rows_read": 5' in result.stdout
    assert '"rows_loaded": 4' in result.stdout


def test_result_of_a_failed_run_exits_with_code_one(
    run_registry: RunRegistry, executor: FakeExecutor
) -> None:
    """A failed run has no result, and scripts must see a failing exit code."""
    _add_run(run_registry)
    executor.state = CallState(
        status=RunStatus.FAILED, dashboard_url=DASHBOARD_URL, error="connection lost"
    )

    result = _invoke("result", "fc-1")

    assert result.exit_code == 1


def test_cancel_stops_the_run_and_reports_it_cancelled(
    run_registry: RunRegistry, executor: FakeExecutor
) -> None:
    """Cancelling must reach Modal and be visible in the output."""
    _add_run(run_registry)

    result = _invoke("cancel", "fc-1")

    assert result.exit_code == 0
    assert executor.cancelled == ["fc-1"]
    assert "cancelled" in result.stdout


def test_cancelling_a_finished_run_exits_with_code_one(
    run_registry: RunRegistry, executor: FakeExecutor
) -> None:
    """There is nothing to cancel, and Modal must not be asked."""
    _add_run(run_registry, status=RunStatus.SUCCEEDED)

    result = _invoke("cancel", "fc-1")

    assert result.exit_code == 1
    assert executor.cancelled == []


# --- staging --------------------------------------------------------------------------------


def test_staging_list_prints_the_staged_files() -> None:
    """Users check what a failed run left behind before cleaning it."""
    result = _invoke("staging", "list")

    assert result.stdout.strip() == "run-1/parquet_path/products.parquet"


def test_staging_clean_removes_the_given_run(volume: FakeVolume) -> None:
    """Cleaning one run must remove exactly that run's directory."""
    result = _invoke("staging", "clean", "run-fc-1")

    assert result.exit_code == 0
    assert volume.removed_directories == [PurePosixPath("run-fc-1")]


def test_staging_clean_refuses_a_run_that_is_still_going(
    run_registry: RunRegistry, volume: FakeVolume
) -> None:
    """Deleting the file under a running task would break it, so the command must refuse."""
    _add_run(run_registry, status=RunStatus.RUNNING)

    result = _invoke("staging", "clean", "run-fc-1")

    assert result.exit_code == 1
    assert volume.removed_directories == []
