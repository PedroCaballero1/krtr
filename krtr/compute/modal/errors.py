"""Defines the error raised when a run on Modal cannot be completed.

Exists so the CLI can catch one exception type for every Modal failure
(the task failed, Modal rejected a request, a run cannot be cancelled)
without importing the optional `modal` SDK, which would break the local path.
Consumed by the executor and the runner, and caught by the CLI commands.
"""


class RemoteExecutionError(Exception):
    """A run on Modal failed, was rejected, or could not be inspected or cancelled.

    Exists as the single, SDK-independent failure type of remote execution.
    Raised by `krtr/compute/modal/executor.py` and `krtr/compute/modal/runner.py`
    and turned into a clean exit code by the CLI commands.
    """
