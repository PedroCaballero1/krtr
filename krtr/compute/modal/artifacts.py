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
    task: RemoteTask
    arguments: dict[str, Any]
    staged_files: list[StagedFile] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: RunStatus


class RemoteRunResult(BaseModel):
    """What a run on Modal reports back to the CLI.

    Exists so callers get a typed outcome instead of parsing log output.
    `result` is whatever the task returned, e.g. a `LoadSummary`, and is None
    while the run is still going or after it failed. Returned by the runner
    and the `status` / `result` operations.
    """

    call_id: str
    dashboard_url: str
    status: RunStatus
    result: BaseModel | None = None
