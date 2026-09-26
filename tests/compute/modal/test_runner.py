"""Tests for running tasks locally or on Modal, and following the runs on Modal."""

import sys
from pathlib import Path, PurePosixPath
from typing import Any

import pytest

from krtr.compute.modal import registry as task_registry
from krtr.compute.modal import runner as runner_module
from krtr.compute.modal.artifacts import CallState, RunRecord, StagedFile
from krtr.compute.modal.config import (
    STAGING_MOUNT_PATH,
    ExecutionMode,
    ModalConfig,
    RemoteTask,
    RunStatus,
)
from krtr.compute.modal.errors import RemoteExecutionError
from krtr.compute.modal.registry import TaskDefinition
from krtr.compute.modal.runner import RemoteRunner, run_task
from krtr.compute.modal.runs import RunRegistry
from krtr.database.neon.artifacts import LoadSummary
from tests.compute.modal.fakes import DASHBOARD_URL, FakeExecutor, FakeVolume

SUMMARY = LoadSummary(rows_read=2, rows_loaded=2)


@pytest.fixture
def parquet(tmp_path: Path) -> Path:
    """A small local file standing in for `data/products.parquet`."""
    path = tmp_path / "products.parquet"
    path.write_bytes(b"data")
    return path


@pytest.fixture
def executor() -> FakeExecutor:
    """A fake Modal executor whose task succeeds with `SUMMARY`."""
    fake = FakeExecutor()
    fake.result = SUMMARY
    return fake


@pytest.fixture
def volume() -> FakeVolume:
    """A fake staging volume."""
    return FakeVolume()


@pytest.fixture
def run_registry(tmp_path: Path) -> RunRegistry:
    """A real run registry over a temporary `.krtr/runs.jsonl`."""
    return RunRegistry(tmp_path / ".krtr" / "runs.jsonl")


@pytest.fixture
def runner(executor: FakeExecutor, volume: FakeVolume, run_registry: RunRegistry) -> RemoteRunner:
    """A runner over the fakes and the temporary registry."""
    return RemoteRunner(executor, volume, run_registry)


def _arguments(parquet: Path) -> dict[str, Any]:
    """The arguments of a `neon-load` run over the given file."""
    return {"table_name": "products", "parquet_path": parquet, "truncate": True}


def _add_run(
    run_registry: RunRegistry,
    call_id: str = "fc-1",
    status: RunStatus = RunStatus.RUNNING,
    staged: bool = False,
) -> RunRecord:
    """Records a run as `--detach` would have left it, optionally with a staged file."""
    record = RunRecord(
        run_id=f"run-{call_id}",
        call_id=call_id,
        dashboard_url=DASHBOARD_URL,
        task=RemoteTask.NEON_LOAD,
        arguments={"table_name": "products"},
        staged_files=(
            [
                StagedFile(
                    local_path=Path("data/products.parquet"),
                    remote_path=PurePosixPath(f"run-{call_id}/parquet_path/products.parquet"),
                )
            ]
            if staged
            else []
        ),
        status=status,
    )
    run_registry.add(record)
    return record


# --- Launching: --remote and --detach ---------------------------------------------------------


def test_detached_run_launches_records_and_returns_without_waiting(
    runner: RemoteRunner,
    executor: FakeExecutor,
    volume: FakeVolume,
    run_registry: RunRegistry,
    parquet: Path,
) -> None:
    """--detach must leave the run going: recorded, staged files kept, nothing awaited."""
    outcome = runner.run(RemoteTask.NEON_LOAD, _arguments(parquet), ExecutionMode.DETACHED)

    assert executor.detach_flags == [True]
    assert executor.session.waited == []
    assert outcome.status is RunStatus.RUNNING
    assert outcome.call_id == "fc-1"
    assert outcome.dashboard_url == DASHBOARD_URL
    assert volume.removed_directories == []
    record = run_registry.get("fc-1")
    assert record.status is RunStatus.RUNNING
    assert record.run_id == outcome.run_id
    assert [file.local_path for file in record.staged_files] == [parquet]


def test_launch_sends_the_staged_path_and_the_tasks_resources(
    runner: RemoteRunner, executor: FakeExecutor, parquet: Path
) -> None:
    """The container must receive the mounted path, never this machine's path."""
    outcome = runner.run(RemoteTask.NEON_LOAD, _arguments(parquet), ExecutionMode.DETACHED)

    task, arguments, resources = executor.session.spawned[0]
    assert task is RemoteTask.NEON_LOAD
    assert arguments["parquet_path"] == (
        STAGING_MOUNT_PATH / outcome.run_id / "parquet_path" / "products.parquet"
    )
    assert arguments["table_name"] == "products"
    assert resources == task_registry.get_task_definition(RemoteTask.NEON_LOAD).resources


def test_remote_run_waits_and_cleans_up_after_success(
    runner: RemoteRunner,
    executor: FakeExecutor,
    volume: FakeVolume,
    run_registry: RunRegistry,
    parquet: Path,
) -> None:
    """--remote must return the task's result, mark the run done and delete its staged file."""
    outcome = runner.run(RemoteTask.NEON_LOAD, _arguments(parquet), ExecutionMode.REMOTE)

    assert executor.detach_flags == [False]
    assert outcome.status is RunStatus.SUCCEEDED
    assert outcome.result == SUMMARY
    assert run_registry.get("fc-1").status is RunStatus.SUCCEEDED
    assert volume.removed_directories == [PurePosixPath(outcome.run_id)]


def test_remote_run_keeps_the_staged_file_when_the_task_fails(
    runner: RemoteRunner,
    executor: FakeExecutor,
    volume: FakeVolume,
    run_registry: RunRegistry,
    parquet: Path,
) -> None:
    """A failed load must keep its file, so it can be retried without uploading again."""
    executor.wait_error = RuntimeError("connection lost")

    with pytest.raises(RemoteExecutionError, match="connection lost") as failure:
        runner.run(RemoteTask.NEON_LOAD, _arguments(parquet), ExecutionMode.REMOTE)

    assert isinstance(failure.value.__cause__, RuntimeError)
    assert run_registry.get("fc-1").status is RunStatus.FAILED
    assert volume.removed_directories == []


def test_interrupting_a_remote_run_records_it_as_cancelled(
    runner: RemoteRunner,
    executor: FakeExecutor,
    volume: FakeVolume,
    run_registry: RunRegistry,
    parquet: Path,
) -> None:
    """Ctrl-C ends the session, which stops the task, so the record must say cancelled."""
    executor.wait_error = KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        runner.run(RemoteTask.NEON_LOAD, _arguments(parquet), ExecutionMode.REMOTE)

    assert run_registry.get("fc-1").status is RunStatus.CANCELLED
    assert volume.removed_directories == []


def test_a_missing_local_file_fails_before_touching_modal(
    runner: RemoteRunner,
    executor: FakeExecutor,
    volume: FakeVolume,
    run_registry: RunRegistry,
    tmp_path: Path,
) -> None:
    """A wrong path must fail on this machine, before any upload, session or record."""
    with pytest.raises(FileNotFoundError):
        runner.run(
            RemoteTask.NEON_LOAD, _arguments(tmp_path / "missing.parquet"), ExecutionMode.REMOTE
        )

    assert volume.uploads == []
    assert executor.detach_flags == []
    assert run_registry.list_runs() == []


def test_a_task_that_never_started_leaves_no_staged_files_and_no_record(
    runner: RemoteRunner,
    executor: FakeExecutor,
    volume: FakeVolume,
    run_registry: RunRegistry,
    parquet: Path,
) -> None:
    """If Modal refuses to start the task, the uploaded file must not be orphaned."""
    executor.spawn_error = RemoteExecutionError("quota exceeded")

    with pytest.raises(RemoteExecutionError, match="quota exceeded"):
        runner.run(RemoteTask.NEON_LOAD, _arguments(parquet), ExecutionMode.DETACHED)

    assert len(volume.uploads) == 1
    assert volume.removed_directories == [volume.uploads[0][1].parents[-2]]
    assert run_registry.list_runs() == []


def test_the_runner_refuses_local_mode(runner: RemoteRunner, parquet: Path) -> None:
    """Local runs never use the runner, so asking it to run locally is a bug to surface."""
    with pytest.raises(ValueError, match="run_task"):
        runner.run(RemoteTask.NEON_LOAD, _arguments(parquet), ExecutionMode.LOCAL)


# --- Following a run: status, result, cancel --------------------------------------------------


def test_status_of_a_running_run_leaves_its_record_alone(
    runner: RemoteRunner,
    executor: FakeExecutor,
    volume: FakeVolume,
    run_registry: RunRegistry,
) -> None:
    """Asking about a run that is still going must not change anything."""
    _add_run(run_registry)

    outcome = runner.get_status("fc-1")

    assert executor.inspections == [("fc-1", False)]
    assert outcome.status is RunStatus.RUNNING
    assert run_registry.get("fc-1").status is RunStatus.RUNNING


def test_status_that_finds_the_run_succeeded_records_it_and_cleans_up(
    runner: RemoteRunner,
    executor: FakeExecutor,
    volume: FakeVolume,
    run_registry: RunRegistry,
    parquet: Path,
) -> None:
    """A --detach run's staged file must be deleted once a status check sees it finished."""
    detached = runner.run(RemoteTask.NEON_LOAD, _arguments(parquet), ExecutionMode.DETACHED)
    executor.state = CallState(
        status=RunStatus.SUCCEEDED, dashboard_url=DASHBOARD_URL, result=SUMMARY
    )

    outcome = runner.get_status("fc-1")

    assert outcome.status is RunStatus.SUCCEEDED
    assert outcome.result == SUMMARY
    assert run_registry.get("fc-1").status is RunStatus.SUCCEEDED
    assert volume.removed_directories == [PurePosixPath(detached.run_id)]


def test_status_that_finds_the_run_failed_records_the_error_and_keeps_the_file(
    runner: RemoteRunner,
    executor: FakeExecutor,
    volume: FakeVolume,
    run_registry: RunRegistry,
    parquet: Path,
) -> None:
    """A failure seen later must be recorded with its reason, and the file kept for a retry."""
    runner.run(RemoteTask.NEON_LOAD, _arguments(parquet), ExecutionMode.DETACHED)
    executor.state = CallState(
        status=RunStatus.FAILED, dashboard_url=DASHBOARD_URL, error="connection lost"
    )

    outcome = runner.get_status("fc-1")

    assert outcome.status is RunStatus.FAILED
    assert outcome.error == "connection lost"
    assert run_registry.get("fc-1").status is RunStatus.FAILED
    assert volume.removed_directories == []


def test_status_of_a_finished_run_does_not_ask_modal(
    runner: RemoteRunner,
    executor: FakeExecutor,
    run_registry: RunRegistry,
) -> None:
    """A run already recorded as finished is answered from the record."""
    _add_run(run_registry)
    run_registry.update_status("fc-1", RunStatus.CANCELLED)

    outcome = runner.get_status("fc-1")

    assert outcome.status is RunStatus.CANCELLED
    assert executor.inspections == []


def test_status_of_an_unknown_call_id_names_it(runner: RemoteRunner) -> None:
    """A mistyped call id must say which id was not found."""
    with pytest.raises(ValueError, match="fc-999"):
        runner.get_status("fc-999")


def test_result_waits_for_the_run_and_returns_the_tasks_result(
    runner: RemoteRunner,
    executor: FakeExecutor,
    run_registry: RunRegistry,
) -> None:
    """`result` must block until the run is done, then return what the task returned."""
    _add_run(run_registry)
    executor.state = CallState(
        status=RunStatus.SUCCEEDED, dashboard_url=DASHBOARD_URL, result=SUMMARY
    )

    outcome = runner.get_result("fc-1")

    assert executor.inspections == [("fc-1", True)]
    assert outcome.result == SUMMARY


def test_result_of_a_failed_run_raises_with_the_reason(
    runner: RemoteRunner,
    executor: FakeExecutor,
    run_registry: RunRegistry,
) -> None:
    """Asking for the result of a failed run must fail loudly, not return an empty result."""
    _add_run(run_registry)
    executor.state = CallState(
        status=RunStatus.FAILED, dashboard_url=DASHBOARD_URL, error="connection lost"
    )

    with pytest.raises(RemoteExecutionError, match="connection lost"):
        runner.get_result("fc-1")


def test_result_of_a_cancelled_run_raises_without_asking_modal(
    runner: RemoteRunner,
    executor: FakeExecutor,
    run_registry: RunRegistry,
) -> None:
    """A cancelled run has no result, and waiting for one would block forever."""
    _add_run(run_registry)
    run_registry.update_status("fc-1", RunStatus.CANCELLED)

    with pytest.raises(RemoteExecutionError, match="cancelled"):
        runner.get_result("fc-1")

    assert executor.inspections == []


def test_cancel_stops_the_call_records_it_and_keeps_the_staged_file(
    runner: RemoteRunner,
    executor: FakeExecutor,
    volume: FakeVolume,
    run_registry: RunRegistry,
    parquet: Path,
) -> None:
    """Cancelling must stop the task on Modal but keep its file, so it can be relaunched."""
    runner.run(RemoteTask.NEON_LOAD, _arguments(parquet), ExecutionMode.DETACHED)

    outcome = runner.cancel("fc-1")

    assert executor.cancelled == ["fc-1"]
    assert outcome.status is RunStatus.CANCELLED
    assert run_registry.get("fc-1").status is RunStatus.CANCELLED
    assert volume.removed_directories == []


def test_cancelling_a_finished_run_is_refused_without_calling_modal(
    runner: RemoteRunner,
    executor: FakeExecutor,
    run_registry: RunRegistry,
) -> None:
    """A run that already finished has nothing to cancel, and Modal must not be asked."""
    _add_run(run_registry)
    run_registry.update_status("fc-1", RunStatus.SUCCEEDED)

    with pytest.raises(ValueError, match="succeeded"):
        runner.cancel("fc-1")

    assert executor.cancelled == []


# --- run_task: the entry point commands use ---------------------------------------------------


def test_local_mode_calls_the_task_directly_and_never_builds_a_modal_runner(
    monkeypatch: pytest.MonkeyPatch, parquet: Path
) -> None:
    """Without --remote a command must behave as before, with no Modal, staging or record."""
    calls: list[dict[str, Any]] = []

    def _function(**arguments: Any) -> LoadSummary:
        calls.append(arguments)
        return SUMMARY

    def _forbidden() -> RemoteRunner:
        raise AssertionError("a local run must not build a Modal runner")

    monkeypatch.setitem(
        task_registry.TASK_REGISTRY, RemoteTask.NEON_LOAD, TaskDefinition(_function)
    )
    monkeypatch.setattr(runner_module, "build_modal_runner", _forbidden)

    outcome = run_task(RemoteTask.NEON_LOAD, _arguments(parquet), ExecutionMode.LOCAL)

    assert calls == [_arguments(parquet)]
    assert outcome.status is RunStatus.SUCCEEDED
    assert outcome.result == SUMMARY
    assert (outcome.call_id, outcome.run_id, outcome.dashboard_url) == (None, None, None)


@pytest.mark.parametrize("mode", [ExecutionMode.REMOTE, ExecutionMode.DETACHED])
def test_remote_modes_go_through_the_modal_runner(
    monkeypatch: pytest.MonkeyPatch,
    runner: RemoteRunner,
    executor: FakeExecutor,
    parquet: Path,
    mode: ExecutionMode,
) -> None:
    """--remote and --detach must reach the runner with the requested mode."""
    monkeypatch.setattr(runner_module, "build_modal_runner", lambda: runner)

    run_task(RemoteTask.NEON_LOAD, _arguments(parquet), mode)

    assert executor.detach_flags == [mode is ExecutionMode.DETACHED]


# --- Staging: list and clean ------------------------------------------------------------------


def test_list_staging_reports_what_the_volume_holds(
    executor: FakeExecutor, run_registry: RunRegistry
) -> None:
    """Users must be able to see which files runs have left on the volume."""
    files = [PurePosixPath("run-1/parquet_path/products.parquet")]

    listed = RemoteRunner(executor, FakeVolume(files), run_registry).list_staging()

    assert listed == files


def test_cleaning_one_run_removes_only_that_runs_files(
    runner: RemoteRunner, volume: FakeVolume, run_registry: RunRegistry
) -> None:
    """Cleaning a failed run must not touch another run's staged files."""
    _add_run(run_registry, "fc-1", RunStatus.FAILED, staged=True)
    _add_run(run_registry, "fc-2", RunStatus.FAILED, staged=True)

    cleaned = runner.clean_staging("run-fc-1")

    assert cleaned == ["run-fc-1"]
    assert volume.removed_directories == [PurePosixPath("run-fc-1")]


def test_cleaning_a_run_that_is_still_running_is_refused(
    runner: RemoteRunner, volume: FakeVolume, run_registry: RunRegistry
) -> None:
    """Its container may still be reading the file, so deleting it would break the run."""
    _add_run(run_registry, "fc-1", RunStatus.RUNNING, staged=True)

    with pytest.raises(ValueError, match="still running"):
        runner.clean_staging("run-fc-1")

    assert volume.removed_directories == []


def test_cleaning_an_id_the_registry_does_not_know_is_allowed(
    runner: RemoteRunner, volume: FakeVolume
) -> None:
    """An orphaned directory seen in `staging list` has no record, and must still be removable."""
    assert runner.clean_staging("orphan") == ["orphan"]
    assert volume.removed_directories == [PurePosixPath("orphan")]


def test_cleaning_everything_skips_running_runs_and_runs_without_staged_files(
    runner: RemoteRunner, volume: FakeVolume, run_registry: RunRegistry
) -> None:
    """Bulk cleaning must remove only what is safe: finished runs that left files behind."""
    _add_run(run_registry, "fc-1", RunStatus.FAILED, staged=True)
    _add_run(run_registry, "fc-2", RunStatus.CANCELLED, staged=True)
    _add_run(run_registry, "fc-3", RunStatus.RUNNING, staged=True)
    _add_run(run_registry, "fc-4", RunStatus.SUCCEEDED, staged=False)

    cleaned = runner.clean_staging(None)

    assert cleaned == ["run-fc-1", "run-fc-2"]
    assert volume.removed_directories == [PurePosixPath("run-fc-1"), PurePosixPath("run-fc-2")]


# --- build_modal_runner -----------------------------------------------------------------------


def test_building_the_runner_without_the_modal_sdk_explains_how_to_install_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Using --remote without the extra must say what to install, not show an ImportError."""
    monkeypatch.setitem(sys.modules, "modal", None)

    with pytest.raises(RemoteExecutionError, match="uv sync --extra modal") as failure:
        runner_module.build_modal_runner()

    assert isinstance(failure.value.__cause__, ImportError)


def test_building_the_runner_uses_the_configured_staging_volume(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The runner must stage on the volume named in the config, not a hardcoded one."""
    volume_names: list[str] = []

    def _volume(name: str) -> FakeVolume:
        volume_names.append(name)
        return FakeVolume()

    monkeypatch.setattr(runner_module, "ModalStagingVolume", _volume)

    built = runner_module.build_modal_runner()

    assert isinstance(built, RemoteRunner)
    assert volume_names == [ModalConfig().staging_volume_name]
