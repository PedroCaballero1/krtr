"""Tests for the Modal executor, using a fake `modal` SDK (it is an optional dependency).

The fake mirrors the real SDK's exception hierarchy, verified against modal 1.5.5: a poll that
finds no result raises the *builtin* `TimeoutError`, while `FunctionTimeoutError` and
`OutputExpiredError` derive from `modal.exception.TimeoutError`, a different class.
"""

import sys
from contextlib import contextmanager
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from krtr.compute.modal.config import RemoteTask, RunStatus, TaskResources
from krtr.compute.modal.errors import RemoteExecutionError
from krtr.compute.modal.executor import ModalExecutor, ModalRunSession


class ModalError(Exception):
    """Stands in for `modal.exception.Error`."""


class ModalTimeoutError(ModalError):
    """Stands in for `modal.exception.TimeoutError`, which is not the builtin one."""


class FunctionTimeoutError(ModalTimeoutError):
    """Stands in for `modal.exception.FunctionTimeoutError`."""


class OutputExpiredError(ModalTimeoutError):
    """Stands in for `modal.exception.OutputExpiredError`."""


class AuthError(ModalError):
    """Stands in for `modal.exception.AuthError`."""


class NotFoundError(ModalError):
    """Stands in for `modal.exception.NotFoundError`."""


class FakeCall:
    """Stands in for a `modal.FunctionCall`, with configurable behaviour."""

    object_id = "fc-1"

    def __init__(self) -> None:
        """Starts as a call that has finished with the result `"summary"`."""
        self.get_outcome: Any = "summary"
        self.dashboard_error: Exception | None = None
        self.cancel_error: Exception | None = None
        self.get_timeouts: list[float | None] = []
        self.cancel_flags: list[bool] = []

    def get(self, timeout: float | None = None) -> Any:
        """Records the timeout, then returns the outcome or raises it if it is an exception."""
        self.get_timeouts.append(timeout)
        if isinstance(self.get_outcome, BaseException):
            raise self.get_outcome
        return self.get_outcome

    def get_dashboard_url(self) -> str:
        """Returns a fixed dashboard link, or raises the configured error."""
        if self.dashboard_error:
            raise self.dashboard_error
        return "https://modal.com/apps/krtr/fc-1"

    def cancel(self, terminate_containers: bool = False) -> None:
        """Records the flag, or raises the configured error."""
        self.cancel_flags.append(terminate_containers)
        if self.cancel_error:
            raise self.cancel_error


class FakeSdk:
    """Holds what the fake SDK records: the call it serves and the app runs it saw."""

    def __init__(self) -> None:
        """Starts with one call and no recorded app runs."""
        self.call = FakeCall()
        self.looked_up_ids: list[str] = []
        self.events: list[str] = []
        self.app_run_error: Exception | None = None
        self.with_options_kwargs: list[dict[str, Any]] = []
        self.spawned: list[tuple[Any, ...]] = []


@pytest.fixture
def sdk(monkeypatch: pytest.MonkeyPatch) -> FakeSdk:
    """Installs a fake `modal` SDK and a fake `krtr.compute.modal.app` in `sys.modules`."""
    fake = FakeSdk()

    @contextmanager
    def enable_output() -> Any:
        fake.events.append("output on")
        yield
        fake.events.append("output off")

    @contextmanager
    def run_app(detach: bool = False) -> Any:
        if fake.app_run_error:
            raise fake.app_run_error
        fake.events.append(f"app.run detach={detach}")
        yield
        fake.events.append("app closed")

    def from_id(call_id: str) -> FakeCall:
        fake.looked_up_ids.append(call_id)
        return fake.call

    def with_options(**kwargs: Any) -> SimpleNamespace:
        fake.with_options_kwargs.append(kwargs)

        def spawn(*arguments: Any) -> FakeCall:
            fake.spawned.append(arguments)
            return fake.call

        return SimpleNamespace(spawn=spawn)

    exception_module = ModuleType("modal.exception")
    for name, cls in [
        ("Error", ModalError),
        ("TimeoutError", ModalTimeoutError),
        ("FunctionTimeoutError", FunctionTimeoutError),
        ("OutputExpiredError", OutputExpiredError),
        ("AuthError", AuthError),
        ("NotFoundError", NotFoundError),
    ]:
        setattr(exception_module, name, cls)
    modal_module = ModuleType("modal")
    modal_module.enable_output = enable_output
    modal_module.FunctionCall = SimpleNamespace(from_id=from_id)
    modal_module.exception = exception_module
    app_module = ModuleType("krtr.compute.modal.app")
    app_module.app = SimpleNamespace(run=run_app)
    app_module.execute_task = SimpleNamespace(with_options=with_options)
    monkeypatch.setitem(sys.modules, "modal", modal_module)
    monkeypatch.setitem(sys.modules, "modal.exception", exception_module)
    monkeypatch.setitem(sys.modules, "krtr.compute.modal.app", app_module)
    return fake


# --- inspect_call ---------------------------------------------------------------------------


def test_a_call_with_no_result_yet_is_reported_as_running(sdk: FakeSdk) -> None:
    """A poll that finds nothing must say running, not failed and not raise."""
    sdk.call.get_outcome = TimeoutError()

    state = ModalExecutor().inspect_call("fc-1", wait=False)

    assert state.status is RunStatus.RUNNING
    assert state.dashboard_url == "https://modal.com/apps/krtr/fc-1"


def test_polling_does_not_block_but_waiting_does(sdk: FakeSdk) -> None:
    """`status` must return at once (timeout 0), `result` must wait indefinitely (no timeout)."""
    ModalExecutor().inspect_call("fc-1", wait=False)
    ModalExecutor().inspect_call("fc-1", wait=True)

    assert sdk.call.get_timeouts == [0, None]


def test_a_finished_call_is_reported_as_succeeded_with_its_result(sdk: FakeSdk) -> None:
    """The task's return value must reach the runner."""
    sdk.call.get_outcome = "summary"

    state = ModalExecutor().inspect_call("fc-1", wait=True)

    assert state.status is RunStatus.SUCCEEDED
    assert state.result == "summary"


def test_a_task_that_exceeded_its_time_limit_is_failed_not_running(sdk: FakeSdk) -> None:
    """A timed-out task must never be mistaken for one that is merely still going."""
    sdk.call.get_outcome = FunctionTimeoutError("300s")

    state = ModalExecutor().inspect_call("fc-1", wait=False)

    assert state.status is RunStatus.FAILED
    assert "time limit" in state.error


def test_an_expired_result_is_reported_as_failed_with_an_explanation(sdk: FakeSdk) -> None:
    """Modal only keeps results for a while; an empty error message would be useless."""
    sdk.call.get_outcome = OutputExpiredError()

    state = ModalExecutor().inspect_call("fc-1", wait=False)

    assert state.status is RunStatus.FAILED
    assert "expired" in state.error


def test_an_error_raised_by_the_task_is_reported_as_failed_with_its_message(
    sdk: FakeSdk,
) -> None:
    """A task that raised must come back as a failed state carrying the reason."""
    sdk.call.get_outcome = ValueError("Table 'products' has no columns")

    state = ModalExecutor().inspect_call("fc-1", wait=True)

    assert state.status is RunStatus.FAILED
    assert state.error == "Table 'products' has no columns"


@pytest.mark.parametrize("error", [AuthError("bad token"), NotFoundError("no such call")])
def test_modal_rejections_are_raised_not_reported_as_a_failed_task(
    sdk: FakeSdk, error: Exception
) -> None:
    """A bad token is not a task failure; it must surface as its own error."""
    sdk.call.get_outcome = error

    with pytest.raises(RemoteExecutionError, match="fc-1"):
        ModalExecutor().inspect_call("fc-1", wait=False)


def test_a_rejection_while_reading_the_dashboard_link_is_raised(sdk: FakeSdk) -> None:
    """The link is read before the result, and its failure must not be hidden."""
    sdk.call.dashboard_error = NotFoundError("no such call")

    with pytest.raises(RemoteExecutionError, match="fc-1"):
        ModalExecutor().inspect_call("fc-1", wait=False)


# --- cancel ---------------------------------------------------------------------------------


def test_cancel_terminates_the_container_so_it_stops_costing_compute(sdk: FakeSdk) -> None:
    """Cancelling the call alone would leave the container running."""
    ModalExecutor().cancel("fc-1")

    assert sdk.looked_up_ids == ["fc-1"]
    assert sdk.call.cancel_flags == [True]


def test_cancel_raises_when_modal_rejects_it(sdk: FakeSdk) -> None:
    """A cancellation that did not happen must not be reported as done."""
    sdk.call.cancel_error = NotFoundError("no such call")

    with pytest.raises(RemoteExecutionError, match="fc-1"):
        ModalExecutor().cancel("fc-1")


# --- session --------------------------------------------------------------------------------


def test_an_attached_session_streams_logs_while_the_app_runs(sdk: FakeSdk) -> None:
    """--remote waits for the result, so it shows the image build and the container's logs."""
    with ModalExecutor().open_session(detach=False):
        sdk.events.append("inside")

    assert sdk.events == [
        "output on",
        "app.run detach=False",
        "inside",
        "app closed",
        "output off",
    ]


def test_a_detached_session_does_not_stream_logs_so_it_returns_at_once(sdk: FakeSdk) -> None:
    """On exit the SDK waits for the log stream to end, which would block --detach until done.

    `detach=True` still reaches Modal, and that is what keeps the task alive after the CLI exits.
    """
    with ModalExecutor().open_session(detach=True):
        sdk.events.append("inside")

    assert sdk.events == ["app.run detach=True", "inside", "app closed"]


def test_the_session_reports_bad_credentials_with_a_hint(sdk: FakeSdk) -> None:
    """A missing or wrong token must point at MODAL_TOKEN_ID / MODAL_TOKEN_SECRET."""
    sdk.app_run_error = AuthError("invalid token")

    with pytest.raises(RemoteExecutionError, match="MODAL_TOKEN_ID"):
        with ModalExecutor().open_session(detach=False):
            pass


def test_spawn_applies_the_tasks_own_resources_and_returns_the_call(sdk: FakeSdk) -> None:
    """Each task must run with its own resources, and the runner must get the call id."""
    resources = TaskResources(cpu=2.0, memory_mebibytes=4096, timeout_seconds=7200, retries=0)

    launched = ModalRunSession().spawn(RemoteTask.NEON_LOAD, {"table_name": "products"}, resources)

    assert sdk.with_options_kwargs == [{"cpu": 2.0, "memory": 4096, "timeout": 7200, "retries": 0}]
    assert sdk.spawned == [(RemoteTask.NEON_LOAD, {"table_name": "products"})]
    assert launched.call_id == "fc-1"
    assert launched.dashboard_url == "https://modal.com/apps/krtr/fc-1"


def test_wait_returns_the_result_of_the_call_it_was_given(sdk: FakeSdk) -> None:
    """Waiting must read the call with the given id and return what the task returned."""
    sdk.call.get_outcome = "summary"

    assert ModalRunSession().wait("fc-9") == "summary"
    assert sdk.looked_up_ids == ["fc-9"]
