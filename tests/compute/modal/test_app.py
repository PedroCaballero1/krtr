"""Tests for the Modal app definition; skipped where the optional `modal` SDK is absent."""

import pytest

pytest.importorskip("modal")

from krtr.compute.modal import app as modal_app  # noqa: E402
from krtr.compute.modal.config import RemoteTask  # noqa: E402


@pytest.mark.filterwarnings("ignore:.*executing locally.*:UserWarning")  # No volume, by design.
def test_execute_task_configures_logging_before_running_the_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The container must set up logging first, or the task's early messages are lost."""
    events: list[str] = []
    monkeypatch.setattr(modal_app, "configure_remote_logging", lambda: events.append("logging"))
    monkeypatch.setattr(
        modal_app,
        "run_registered_task",
        lambda task, arguments: events.append(f"run {task.value}") or "summary",
    )

    result = modal_app.execute_task.local(RemoteTask.NEON_LOAD, {"table_name": "products"})

    assert result == "summary"
    assert events == ["logging", "run neon-load"]
