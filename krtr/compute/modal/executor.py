"""Launches tasks on Modal and inspects the calls they create.

Exists to keep everything that talks to the Modal SDK behind two small
interfaces, so the runner can be tested with fakes and the local path never
imports `modal`. The SDK is imported only when a method runs, never at module
level. Consumed by `krtr/compute/modal/runner.py`.
"""

import logging
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager, nullcontext
from typing import Any, Protocol

from krtr.compute.modal.artifacts import CallState, LaunchedCall
from krtr.compute.modal.config import RemoteTask, RunStatus, TaskResources
from krtr.compute.modal.errors import RemoteExecutionError

logger = logging.getLogger(__name__)

AUTHENTICATION_HINT = "check MODAL_TOKEN_ID and MODAL_TOKEN_SECRET (or run `modal token new`)"


class RunSession(Protocol):
    """A live connection to Modal in which tasks can be launched and awaited.

    Exists because an ephemeral Modal app only lives while its context is
    open, so launching and waiting must happen inside it. Implemented by
    `ModalRunSession`; consumed by the runner.
    """

    def spawn(
        self, task: RemoteTask, arguments: dict[str, Any], resources: TaskResources
    ) -> LaunchedCall:
        """Starts a task on Modal without waiting for it to finish.

        Args:
            task: The task to run.
            arguments: The keyword arguments for the task's function.
            resources: The compute resources and limits to run it with.

        Returns:
            LaunchedCall: the call id and dashboard link of the started task.
        """

    def wait(self, call_id: str) -> Any:
        """Blocks until a launched task finishes and returns its result.

        Args:
            call_id: The Modal call id returned by `spawn`.

        Returns:
            Any: the task's return value.

        Raises:
            Exception: whatever the task raised on Modal.
        """


class TaskExecutor(Protocol):
    """The operations the runner needs from Modal.

    Exists so the runner depends on three operations instead of the SDK.
    Implemented by `ModalExecutor`; consumed by the runner.
    """

    def open_session(self, detach: bool) -> AbstractContextManager[RunSession]:
        """Opens a session in which tasks can be launched.

        Args:
            detach: When True, launched tasks keep running after the session
                closes and this process exits.

        Returns:
            AbstractContextManager[RunSession]: the session, closed on exit.
        """

    def inspect_call(self, call_id: str, wait: bool) -> CallState:
        """Reads what Modal reports about a call.

        Args:
            call_id: The Modal call id to inspect.
            wait: When True, block until the call finishes; when False, report
                it as running if it has not.

        Returns:
            CallState: the call's status, plus its result or error once finished.
        """

    def cancel(self, call_id: str) -> None:
        """Cancels a call and stops the container running it.

        Args:
            call_id: The Modal call id to cancel.

        Returns:
            None.
        """


class ModalRunSession:
    """A session on the ephemeral Modal app, launching tasks through `execute_task`.

    Exists so spawning applies the task's own resources on every call while the
    app definition stays generic. Created by `ModalExecutor.open_session` and
    consumed by the runner.
    """

    def spawn(
        self, task: RemoteTask, arguments: dict[str, Any], resources: TaskResources
    ) -> LaunchedCall:
        """Starts a task on Modal with its own resources, without waiting.

        Args:
            task: The task to run.
            arguments: The keyword arguments for the task's function.
            resources: The compute resources and limits to run it with.

        Returns:
            LaunchedCall: the call id and dashboard link of the started task.
        """
        from krtr.compute.modal.app import execute_task

        function = execute_task.with_options(
            cpu=resources.cpu,
            memory=resources.memory_mebibytes,
            timeout=resources.timeout_seconds,
            retries=resources.retries,
        )
        call = function.spawn(task, arguments)
        logger.info("Launched task %s as Modal call %s", task.value, call.object_id)
        return LaunchedCall(call_id=call.object_id, dashboard_url=call.get_dashboard_url())

    def wait(self, call_id: str) -> Any:
        """Blocks until a launched task finishes and returns its result.

        Args:
            call_id: The Modal call id returned by `spawn`.

        Returns:
            Any: the task's return value.

        Raises:
            Exception: whatever the task raised on Modal.
        """
        import modal

        return modal.FunctionCall.from_id(call_id).get()


class ModalExecutor:
    """Runs tasks on Modal through an ephemeral app.

    Exists as the only class that opens Modal sessions and reads or cancels
    calls, so the SDK stays behind the `TaskExecutor` interface. Consumed by
    the runner, which builds it only for `--remote` and `--detach` runs.
    """

    @contextmanager
    def open_session(self, detach: bool) -> Iterator[RunSession]:
        """Runs the Modal app, streaming its logs, for the duration of the block.

        Exists because `detach=True` is what keeps a launched task running
        after the CLI exits, and `enable_output` is what shows the image build
        and container logs while waiting. Output is enabled only when not
        detaching: on a normal exit the SDK waits for the app's log stream to
        end, which would make `--detach` block until the task finished.

        Args:
            detach: When True, launched tasks keep running after the session closes.

        Yields:
            RunSession: a session in which tasks can be launched.

        Raises:
            RemoteExecutionError: if Modal rejects the credentials.
        """
        import modal
        from modal.exception import AuthError

        from krtr.compute.modal.app import app

        output = nullcontext() if detach else modal.enable_output()
        try:
            with output, app.run(detach=detach):
                yield ModalRunSession()
        except AuthError as error:
            raise RemoteExecutionError(
                f"Modal authentication failed; {AUTHENTICATION_HINT}"
            ) from error

    def inspect_call(self, call_id: str, wait: bool) -> CallState:
        """Reads what Modal reports about a call, without raising for a failed task.

        Exists so a task that failed is reported as a state, with its error,
        rather than as an exception in the middle of a status check. A task
        that exceeded its time limit counts as failed, not as still running.

        Args:
            call_id: The Modal call id to inspect.
            wait: When True, block until the call finishes; when False, report
                it as running if it has not.

        Returns:
            CallState: the call's status, plus its result or error once finished.

        Raises:
            RemoteExecutionError: if Modal rejects the credentials or does not know the call.
        """
        import modal
        from modal.exception import AuthError, NotFoundError

        call = modal.FunctionCall.from_id(call_id)
        try:
            return _read_state(call, call.get_dashboard_url(), wait)
        except (AuthError, NotFoundError) as error:
            raise RemoteExecutionError(f"Modal could not read call {call_id}: {error}") from error

    def cancel(self, call_id: str) -> None:
        """Cancels a call and terminates the container running it.

        Exists so a cancelled run stops consuming compute immediately.

        Args:
            call_id: The Modal call id to cancel.

        Returns:
            None.

        Raises:
            RemoteExecutionError: if Modal rejects the credentials or does not know the call.
        """
        import modal
        from modal.exception import AuthError, NotFoundError

        try:
            modal.FunctionCall.from_id(call_id).cancel(terminate_containers=True)
        except (AuthError, NotFoundError) as error:
            raise RemoteExecutionError(f"Modal could not cancel call {call_id}: {error}") from error
        logger.info("Cancelled Modal call %s", call_id)


def _read_state(call: Any, dashboard_url: str, wait: bool) -> CallState:
    """Reads a call's result and turns the outcome into a state.

    Exists so a failed task is a state with its error, and so the cases that
    look alike are told apart: a poll that finds no result yet raises the
    builtin `TimeoutError` (the task is still running), whereas
    `FunctionTimeoutError` (the task exceeded its own limit) and
    `OutputExpiredError` (Modal no longer holds the result) are failures.

    Args:
        call: The Modal function call to read.
        dashboard_url: The call's dashboard link.
        wait: When True, block until the call finishes; when False, poll once.

    Returns:
        CallState: running, succeeded with the result, or failed with the error.

    Raises:
        AuthError: if Modal rejects the credentials.
        NotFoundError: if Modal does not know the call.
    """
    from modal.exception import (
        AuthError,
        FunctionTimeoutError,
        NotFoundError,
        OutputExpiredError,
    )

    try:
        result = call.get(timeout=None if wait else 0)
    except FunctionTimeoutError as error:
        return _failed_state(dashboard_url, f"The task exceeded its time limit: {error}")
    except OutputExpiredError:
        return _failed_state(dashboard_url, "Modal no longer holds this run's result; it expired")
    except TimeoutError:
        return CallState(status=RunStatus.RUNNING, dashboard_url=dashboard_url)
    except (AuthError, NotFoundError):
        raise
    except Exception as error:
        return _failed_state(dashboard_url, str(error))
    return CallState(status=RunStatus.SUCCEEDED, dashboard_url=dashboard_url, result=result)


def _failed_state(dashboard_url: str, error: str) -> CallState:
    """Builds the state of a call whose task failed.

    Args:
        dashboard_url: The call's dashboard link.
        error: Why the task failed.

    Returns:
        CallState: a failed state carrying the error message.
    """
    return CallState(status=RunStatus.FAILED, dashboard_url=dashboard_url, error=error)
