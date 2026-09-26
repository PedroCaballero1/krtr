"""Defines the configuration and option sets for running commands on Modal.

Exists to keep every tunable of remote execution (where a command runs, which
tasks may run remotely, which environment variables travel to the container,
what resources a task gets) in one place, declared with enums and pydantic
models instead of scattered literals. Consumed by the rest of
`krtr/compute/modal/` (registry, runner, secrets, app) and by the CLI helper
under `krtr/cli/compute/modal/`.
"""

from enum import StrEnum
from pathlib import Path, PurePosixPath

from pydantic import BaseModel, Field

from krtr.database.neon.config import NeonEnvironmentVariable

# Repository root, where the git-ignored `.krtr/` directory for local CLI state lives.
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]

# Where the staging volume is mounted inside the Modal container.
STAGING_MOUNT_PATH = PurePosixPath("/staging")

# Python version of the Modal container; matches `requires-python` in `pyproject.toml`.
CONTAINER_PYTHON_VERSION = "3.13"

# Patterns excluded when copying the `krtr` package into the container image. Modal's default
# skips every non-Python file, which would drop the `.sql` files the Neon commands read.
IMAGE_SOURCE_IGNORE_PATTERNS = ("**/__pycache__", "**/*.pyc")


class ExecutionMode(StrEnum):
    """Where a CLI command runs.

    Exists so the local and Modal paths are selected by one explicit value
    rather than scattered booleans. Consumed by the task runner and by the
    `--remote` / `--detach` CLI option.
    """

    LOCAL = "local"  # Runs on this machine, exactly as the command always has.
    REMOTE = "remote"  # Runs on Modal; the CLI waits and streams the logs.
    DETACHED = "detached"  # Runs on Modal; the CLI prints the call id and exits.


class RemoteTask(StrEnum):
    """The tasks that can be dispatched to Modal.

    Exists so the single remote function selects its work from a closed set
    instead of arbitrary strings or callables. Consumed by the task registry,
    the runner and the run records.
    """

    NEON_LOAD = "neon-load"


class ForwardedSecretVariable(StrEnum):
    """The environment variables copied from `.env` into the Modal secret.

    Exists so only an explicit allowlist ever leaves the machine; the whole
    `.env` is never forwarded. Consumed by the secret sync and the doctor.
    """

    NEON_DB_HOST = NeonEnvironmentVariable.CONNECTION_STRING.value


class RunStatus(StrEnum):
    """The lifecycle state of a run launched on Modal.

    Exists so run records and status reports use one vocabulary. Consumed by
    the run registry and the `status` / `runs` commands.
    """

    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DoctorCheckName(StrEnum):
    """The checks `krtr compute modal doctor` runs, by the name it reports them under.

    Exists so the report and its tests refer to each check by one value instead
    of repeating display strings. Consumed by the doctor and the CLI command
    that prints its report.
    """

    NEON_CONNECTION = "Neon connection"  # Needed by local and remote runs alike.
    MODAL_CREDENTIALS = "Modal credentials"  # Needed only for --remote / --detach.
    MODAL_SECRET = "Modal secret"  # Needed only for --remote / --detach.


class TaskResources(BaseModel):
    """The compute resources and limits a remote task runs with.

    Exists so each task declares what it needs instead of relying on Modal's
    defaults. `retries` defaults to zero because retrying a partially applied
    load could insert duplicate rows. Consumed by the task registry and
    applied by the runner on every call.
    """

    cpu: float = Field(default=1.0, gt=0)
    memory_mebibytes: int = Field(default=1024, gt=0)
    timeout_seconds: int = Field(default=3600, gt=0)
    retries: int = Field(default=0, ge=0)


class ModalConfig(BaseModel):
    """The names and locations krtr uses on Modal and on the local machine.

    Exists so the app, secret, staging volume, region and run-record file are
    configured in one typed object rather than hardcoded where they are used.
    `region` is None until set, which lets Modal choose. Consumed by the app
    definition, the runner, the secret sync and the doctor.
    """

    app_name: str = "krtr"
    secret_name: str = "krtr-neon"
    staging_volume_name: str = "krtr-staging"
    region: str | None = None
    runs_file: Path = REPOSITORY_ROOT / ".krtr" / "runs.jsonl"
