"""Runs registered tasks locally or on Modal, and follows the runs on Modal.

Exists as the one helper any command uses to run on Modal: it stages the task's
local files, launches the task, records the run, and later reports, fetches or
cancels it by call id. In local mode it calls the task's function directly and
never touches Modal, so a command behaves exactly as it always has. Consumed by
the CLI commands (through `run_task`) and by the `krtr compute modal` commands
(through `RemoteRunner`).
"""

import logging
import uuid
from typing import Any

from krtr.compute.modal.artifacts import CallState, RunOutcome, RunRecord, StagingResult
from krtr.compute.modal.config import ExecutionMode, ModalConfig, RemoteTask, RunStatus
from krtr.compute.modal.dispatch import run_registered_task
from krtr.compute.modal.errors import RemoteExecutionError
from krtr.compute.modal.executor import ModalExecutor, RunSession, TaskExecutor
from krtr.compute.modal.registry import get_task_definition
from krtr.compute.modal.runs import RunRegistry
from krtr.compute.modal.staging import StagingVolume, remove_run_staging, stage_task_files
from krtr.compute.modal.volume import ModalStagingVolume

logger = logging.getLogger(__name__)

RUN_ID_LENGTH = 12


class RemoteRunner:
    """Launches tasks on Modal and follows the runs it launched.

    Exists to keep the whole lifecycle of a remote run in one place: staging,
    launching, recording, waiting, cleaning up after success, and keeping the
    staged files after a failure or cancellation so the run can be retried
    without uploading again. Consumed by `run_task` and by the
    `krtr compute modal` commands.
    """

    def __init__(
        self, executor: TaskExecutor, volume: StagingVolume, registry: RunRegistry
    ) -> None:
        """Wires the runner to Modal, the staging volume and the run registry.

        Args:
            executor: Launches tasks and inspects calls on Modal.
            volume: The volume local files are staged on.
            registry: The local record of runs.
        """
        self._executor = executor
        self._volume = volume
        self._registry = registry

    def run(self, task: RemoteTask, arguments: dict[str, Any], mode: ExecutionMode) -> RunOutcome:
        """Stages a task's files, launches it on Modal and records the run.

        Exists as the entry point for `--remote` (wait for the result, streaming
        logs) and `--detach` (return as soon as the task has started).

        Args:
            task: The task to run.
            arguments: The task's keyword arguments, with local file paths.
            mode: `REMOTE` to wait for the result, `DETACHED` to return once launched.

        Returns:
            RunOutcome: the finished run for `REMOTE`, or the running one for `DETACHED`.

        Raises:
            ValueError: if `mode` is `LOCAL`, which never uses the runner.
            FileNotFoundError: if a local file the task needs does not exist.
            RemoteExecutionError: if the task fails on Modal.
        """
        if mode is ExecutionMode.LOCAL:
            raise ValueError("RemoteRunner only runs on Modal; use run_task for local runs")
        definition = get_task_definition(task)
        run_id = uuid.uuid4().hex[:RUN_ID_LENGTH]
        staging = stage_task_files(self._volume, definition, arguments, run_id)
        detach = mode is ExecutionMode.DETACHED
        with self._executor.open_session(detach) as session:
            record = self._launch(session, task, arguments, staging, run_id)
            if detach:
                return self._outcome(record, RunStatus.RUNNING)
            return self._await(session, record)

    def get_status(self, call_id: str) -> RunOutcome:
        """Reports where a run launched earlier stands, updating its record.

        Exists for the `status` command. A run already recorded as finished is
        reported from the record, without asking Modal.

        Args:
            call_id: The Modal call id printed when the run was launched.

        Returns:
            RunOutcome: the run's status, with its result or error once finished.

        Raises:
            ValueError: if no run was recorded with that call id.
            RemoteExecutionError: if Modal cannot be read.
        """
        record = self._registry.get(call_id)
        if record.status is not RunStatus.RUNNING:
            return self._outcome(record, record.status)
        return self._apply_state(record, self._executor.inspect_call(call_id, wait=False))

    def get_result(self, call_id: str) -> RunOutcome:
        """Waits for a run launched earlier and returns its result.

        Exists for the `result` command, so a `--detach` run's outcome can be
        fetched later, whenever it finishes.

        Args:
            call_id: The Modal call id printed when the run was launched.

        Returns:
            RunOutcome: the finished run, with the task's result.

        Raises:
            ValueError: if no run was recorded with that call id.
            RemoteExecutionError: if the run was cancelled or failed, or Modal cannot be read.
        """
        record = self._registry.get(call_id)
        if record.status is RunStatus.CANCELLED:
            raise RemoteExecutionError(f"Run {call_id} was cancelled and has no result")
        outcome = self._apply_state(record, self._executor.inspect_call(call_id, wait=True))
        if outcome.status is RunStatus.FAILED:
            raise RemoteExecutionError(f"Run {call_id} failed: {outcome.error}")
        return outcome

    def cancel(self, call_id: str) -> RunOutcome:
        """Cancels a run that is still going and records it as cancelled.

        Exists for the `cancel` command. The run's staged files are kept, so it
        can be launched again without uploading them.

        Args:
            call_id: The Modal call id printed when the run was launched.

        Returns:
            RunOutcome: the run, now cancelled.

        Raises:
            ValueError: if no run was recorded with that call id, or it is not running.
            RemoteExecutionError: if Modal cannot cancel the call.
        """
        record = self._registry.get(call_id)
        if record.status is not RunStatus.RUNNING:
            raise ValueError(f"Run {call_id} is {record.status.value}: there is nothing to cancel")
        self._executor.cancel(call_id)
        self._registry.update_status(call_id, RunStatus.CANCELLED)
        return self._outcome(record, RunStatus.CANCELLED)

    def _launch(
        self,
        session: RunSession,
        task: RemoteTask,
        arguments: dict[str, Any],
        staging: StagingResult,
        run_id: str,
    ) -> RunRecord:
        """Spawns the task and records the run the moment it has started.

        Exists so a run is recorded before anything can go wrong while waiting,
        and so a task that never started does not leave staged files behind.

        Args:
            session: The open Modal session.
            task: The task to run.
            arguments: The task's arguments as given, with local paths, for the record.
            staging: The rewritten arguments and uploaded files.
            run_id: The id of this run.

        Returns:
            RunRecord: the recorded run, marked as running.
        """
        definition = get_task_definition(task)
        try:
            launched = session.spawn(task, staging.arguments, definition.resources)
        except Exception:
            if staging.staged_files:
                remove_run_staging(self._volume, run_id)
            raise
        record = RunRecord(
            run_id=run_id,
            call_id=launched.call_id,
            dashboard_url=launched.dashboard_url,
            task=task,
            arguments=arguments,
            staged_files=staging.staged_files,
            status=RunStatus.RUNNING,
        )
        self._registry.add(record)
        logger.info("Run %s started; follow it at %s", run_id, launched.dashboard_url)
        return record

    def _await(self, session: RunSession, record: RunRecord) -> RunOutcome:
        """Waits for a launched task and settles its record.

        Exists so a failed or interrupted run is recorded as such, keeping its
        staged files, while a successful one is cleaned up.

        Args:
            session: The open Modal session.
            record: The run that was just launched.

        Returns:
            RunOutcome: the succeeded run, with the task's result.

        Raises:
            RemoteExecutionError: if the task failed on Modal.
            KeyboardInterrupt: if the user interrupted the wait; the run is
                recorded as cancelled, since closing the session stops it.
        """
        try:
            result = session.wait(record.call_id)
        except KeyboardInterrupt:
            self._registry.update_status(record.call_id, RunStatus.CANCELLED)
            raise
        except Exception as error:
            self._registry.update_status(record.call_id, RunStatus.FAILED)
            raise RemoteExecutionError(
                f"Run {record.run_id} failed on Modal: {error}. Its staged files were kept."
            ) from error
        self._finish(record)
        return self._outcome(record, RunStatus.SUCCEEDED, result=result)

    def _apply_state(self, record: RunRecord, state: CallState) -> RunOutcome:
        """Updates a run's record from what Modal reports, and builds the outcome.

        Args:
            record: The recorded run.
            state: What Modal currently reports about its call.

        Returns:
            RunOutcome: the run's status, with its result or error once finished.
        """
        if state.status is RunStatus.SUCCEEDED and record.status is not RunStatus.SUCCEEDED:
            self._finish(record)
        elif state.status is RunStatus.FAILED and record.status is not RunStatus.FAILED:
            self._registry.update_status(record.call_id, RunStatus.FAILED)
        return self._outcome(record, state.status, result=state.result, error=state.error)

    def _outcome(
        self,
        record: RunRecord,
        status: RunStatus,
        result: Any = None,
        error: str | None = None,
    ) -> RunOutcome:
        """Builds the outcome of a recorded run.

        Exists so every operation reports a run with the same identifying fields.

        Args:
            record: The recorded run.
            status: The status to report, which may be newer than the record's.
            result: The task's result, once it has finished.
            error: Why the run failed, if it did.

        Returns:
            RunOutcome: the run's ids, dashboard link, status and result or error.
        """
        return RunOutcome(
            status=status,
            result=result,
            run_id=record.run_id,
            call_id=record.call_id,
            dashboard_url=record.dashboard_url,
            error=error,
        )

    def _finish(self, record: RunRecord) -> None:
        """Records a run as succeeded and removes the files staged for it.

        Args:
            record: The run that succeeded.

        Returns:
            None.
        """
        self._registry.update_status(record.call_id, RunStatus.SUCCEEDED)
        if record.staged_files:
            remove_run_staging(self._volume, record.run_id)


def build_modal_runner() -> RemoteRunner:
    """Builds a runner wired to the real Modal executor, volume and run registry.

    Exists so the Modal SDK is reached only when a command actually runs
    remotely: the executor and volume classes import it when used, not here.

    Returns:
        RemoteRunner: a runner using the default `ModalConfig`.
    """
    config = ModalConfig()
    return RemoteRunner(
        ModalExecutor(),
        ModalStagingVolume(config.staging_volume_name),
        RunRegistry(config.runs_file),
    )


def run_task(task: RemoteTask, arguments: dict[str, Any], mode: ExecutionMode) -> RunOutcome:
    """Runs a registered task in the requested mode.

    Exists as the single call a command makes to gain `--remote` and `--detach`:
    local mode calls the task's function directly, through the same path
    the remote container uses, and never builds a Modal runner.

    Args:
        task: The task to run.
        arguments: The task's keyword arguments, with local file paths.
        mode: Where to run it.

    Returns:
        RunOutcome: the task's outcome; a running one for a detached run.

    Raises:
        FileNotFoundError: if a local file a remote run needs does not exist.
        RemoteExecutionError: if a remote run fails.
    """
    if mode is ExecutionMode.LOCAL:
        result = run_registered_task(task, arguments)
        return RunOutcome(status=RunStatus.SUCCEEDED, result=result)
    return build_modal_runner().run(task, arguments, mode)
