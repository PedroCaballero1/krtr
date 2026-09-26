"""Formats runs, tasks and checks for the terminal.

Exists to keep presentation out of the command functions, so they stay thin:
parse input, call the vertical, print the result. Consumed by the
`krtr compute modal` commands and by any command that can run on Modal.
"""

import logging
from enum import StrEnum

from krtr.compute.modal.artifacts import DoctorCheck, RunOutcome, RunRecord
from krtr.compute.modal.config import RemoteTask
from krtr.compute.modal.registry import TaskDefinition

logger = logging.getLogger(__name__)


class CheckMarker(StrEnum):
    """The label printed in front of each doctor check.

    Exists so the report's two outcomes are named values rather than repeated
    literals. Consumed by `format_check`.
    """

    PASSED = "ok    "
    FAILED = "FAILED"


def format_check(check: DoctorCheck) -> str:
    """Formats one doctor check as a line.

    Args:
        check: The check to format.

    Returns:
        str: the marker, the check's name and its detail.
    """
    marker = CheckMarker.PASSED if check.passed else CheckMarker.FAILED
    return f"{marker}  {check.name.value}: {check.detail}"


def describe_task(task: RemoteTask, definition: TaskDefinition) -> str:
    """Formats a registered task with the resources it runs with.

    Args:
        task: The task's name.
        definition: The task's definition.

    Returns:
        str: the name, resources and the arguments uploaded from this machine.
    """
    resources = definition.resources
    local_files = ", ".join(definition.local_file_arguments) or "none"
    return (
        f"{task.value}  cpu={resources.cpu}  memory={resources.memory_mebibytes}MiB  "
        f"timeout={resources.timeout_seconds}s  retries={resources.retries}  "
        f"uploads: {local_files}"
    )


def describe_run(record: RunRecord) -> str:
    """Formats a recorded run as one line.

    Args:
        record: The recorded run.

    Returns:
        str: the call id, run id, task, status and start time.
    """
    started = record.created_at.strftime("%Y-%m-%d %H:%M:%S")
    return (
        f"{record.call_id}  {record.run_id}  {record.task.value}  {record.status.value}  {started}"
    )


def describe_outcome(outcome: RunOutcome) -> str:
    """Formats the state of a run as one line.

    Args:
        outcome: The run's outcome.

    Returns:
        str: the call id and status, plus the error and dashboard link when known.
    """
    parts = [f"{outcome.call_id}  {outcome.status.value}"]
    if outcome.error:
        parts.append(f"error: {outcome.error}")
    if outcome.dashboard_url:
        parts.append(outcome.dashboard_url)
    return "  ".join(parts)


def report_launched(outcome: RunOutcome) -> None:
    """Logs that a run was started on Modal and how to follow it.

    Exists so `--detach` tells the user what to do next, since the command
    returns before the task has finished.

    Args:
        outcome: The outcome of the run that was just launched.

    Returns:
        None.
    """
    logger.info("Run %s started on Modal (call %s)", outcome.run_id, outcome.call_id)
    logger.info("Dashboard: %s", outcome.dashboard_url)
    logger.info("Follow it with: krtr compute modal status %s", outcome.call_id)
