"""Defines the structured values produced and stored by Modal execution.

Exists to keep the contracts of remote execution (what was staged, what a run
record holds, what a finished run reports) discoverable apart from the
implementation. Consumed by the staging, run registry and runner modules of
`krtr/compute/modal/` and by the CLI commands that report them.
"""

from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from pydantic import BaseModel, Field

from krtr.compute.modal.config import RemoteTask, RunStatus


class StagedFile(BaseModel):
    """A local file uploaded to the staging volume for a remote run.

    Exists so a run remembers which local file went where, letting the runner
    rewrite the task's arguments and later clean the volume. Returned by the
    staging upload and stored in `RunRecord`.
    """

    local_path: Path
    remote_path: PurePosixPath  # Path in the volume: `<run-id>/<argument>/<file name>`.


class StagingResult(BaseModel):
    """The outcome of staging a task's local files for a remote run.

    Exists so the runner receives, in one value, the arguments to send to Modal
    (with each local file path replaced by its path inside the container) and
    the files that were uploaded. Returned by the staging step and consumed by
    the runner.
    """

    arguments: dict[str, Any]
    staged_files: list[StagedFile]


class RunRecord(BaseModel):
    """One run launched on Modal, as kept in the local run registry.

    Exists so `runs`, `status`, `result` and `cancel` can find a run later
    from its call id, and so a failed run's staged files can be located.
    `run_id` is created locally before the call id exists, since the files
    are staged before the task is dispatched. `arguments` are stored as
    given, so paths are written as strings. Persisted one per line in
    `.krtr/runs.jsonl`.
    """

    run_id: str
    call_id: str
    dashboard_url: str
    task: RemoteTask
    arguments: dict[str, Any]
    staged_files: list[StagedFile] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: RunStatus


class LaunchedCall(BaseModel):
    """A task that Modal has accepted and started.

    Exists so the runner learns the call id and dashboard link the moment a
    task is launched, before it finishes, and can record the run right away.
    Returned by the executor when it spawns a task.
    """

    call_id: str
    dashboard_url: str


class CallState(BaseModel):
    """What Modal currently reports about one call.

    Exists so the runner reads a call's progress without touching the Modal
    SDK. `result` is set once the call succeeded and `error` once it failed.
    Returned by the executor when a call is inspected.
    """

    status: RunStatus
    dashboard_url: str
    result: Any = None
    error: str | None = None


class RunOutcome(BaseModel):
    """What running a task reports back to the CLI, locally or on Modal.

    Exists so every command reports a run the same way whatever the mode.
    `result` is the task's return value (a pydantic model such as a
    `LoadSummary`), set once it has finished. `run_id`, `call_id` and
    `dashboard_url` are None for a local run, which has no Modal call, and
    `error` says why a run failed. Returned by the runner and by the `status`,
    `result` and `cancel` operations.
    """

    status: RunStatus
    result: BaseModel | None = None
    run_id: str | None = None
    call_id: str | None = None
    dashboard_url: str | None = None
    error: str | None = None
