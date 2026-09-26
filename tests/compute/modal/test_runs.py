"""Tests for the local registry of runs launched on Modal."""

from pathlib import Path

import pytest

from krtr.compute.modal.artifacts import RunRecord
from krtr.compute.modal.config import RemoteTask, RunStatus
from krtr.compute.modal.runs import RunRegistry


def _record(call_id: str, status: RunStatus = RunStatus.RUNNING) -> RunRecord:
    """Builds a `neon-load` run record whose run id is derived from its call id."""
    return RunRecord(
        run_id=f"run-{call_id}",
        call_id=call_id,
        dashboard_url=f"https://modal.com/apps/krtr/{call_id}",
        task=RemoteTask.NEON_LOAD,
        arguments={"table_name": "products"},
        status=status,
    )


@pytest.fixture
def registry(tmp_path: Path) -> RunRegistry:
    """A registry over a `.krtr/runs.jsonl` that does not exist yet."""
    return RunRegistry(tmp_path / ".krtr" / "runs.jsonl")


def test_list_runs_is_empty_and_creates_nothing_before_the_first_run(
    registry: RunRegistry, tmp_path: Path
) -> None:
    """Listing must not create `.krtr/` for a user who never launched a remote run."""
    assert registry.list_runs() == []
    assert not (tmp_path / ".krtr").exists()


def test_added_runs_are_listed_oldest_first_and_survive_a_new_registry(
    registry: RunRegistry, tmp_path: Path
) -> None:
    """Runs recorded by one CLI invocation must be visible to the next one."""
    registry.add(_record("fc-1"))
    registry.add(_record("fc-2"))

    reopened = RunRegistry(tmp_path / ".krtr" / "runs.jsonl")

    assert [record.call_id for record in reopened.list_runs()] == ["fc-1", "fc-2"]


def test_get_returns_the_run_with_the_given_call_id(registry: RunRegistry) -> None:
    """Looking a run up must return that run, not the first or last one."""
    for call_id in ("fc-1", "fc-2", "fc-3"):
        registry.add(_record(call_id))

    assert registry.get("fc-2").run_id == "run-fc-2"


def test_get_unknown_call_id_names_the_missing_id(registry: RunRegistry) -> None:
    """A mistyped call id must produce a message that says which id was not found."""
    registry.add(_record("fc-1"))

    with pytest.raises(ValueError, match="fc-999"):
        registry.get("fc-999")


def test_update_status_changes_only_the_target_run_and_persists(
    registry: RunRegistry, tmp_path: Path
) -> None:
    """Finishing one run must not alter another, and must be saved to disk."""
    registry.add(_record("fc-1"))
    registry.add(_record("fc-2"))

    updated = registry.update_status("fc-2", RunStatus.SUCCEEDED)

    reopened = RunRegistry(tmp_path / ".krtr" / "runs.jsonl")
    assert updated.status is RunStatus.SUCCEEDED
    assert [(r.call_id, r.status) for r in reopened.list_runs()] == [
        ("fc-1", RunStatus.RUNNING),
        ("fc-2", RunStatus.SUCCEEDED),
    ]


def test_update_status_leaves_no_temporary_file_behind(
    registry: RunRegistry, tmp_path: Path
) -> None:
    """The atomic rewrite must clean up after itself."""
    registry.add(_record("fc-1"))

    registry.update_status("fc-1", RunStatus.FAILED)

    assert sorted(path.name for path in (tmp_path / ".krtr").iterdir()) == ["runs.jsonl"]


def test_update_status_of_unknown_run_leaves_the_file_untouched(
    registry: RunRegistry, tmp_path: Path
) -> None:
    """A failed update must not rewrite or lose the runs that are recorded."""
    registry.add(_record("fc-1"))
    runs_file = tmp_path / ".krtr" / "runs.jsonl"
    before = runs_file.read_text()

    with pytest.raises(ValueError, match="fc-999"):
        registry.update_status("fc-999", RunStatus.CANCELLED)

    assert runs_file.read_text() == before


def test_blank_lines_are_ignored(registry: RunRegistry, tmp_path: Path) -> None:
    """A stray empty line, e.g. from a manual edit, must not break listing."""
    registry.add(_record("fc-1"))
    runs_file = tmp_path / ".krtr" / "runs.jsonl"
    runs_file.write_text(runs_file.read_text() + "\n\n")

    assert [record.call_id for record in registry.list_runs()] == ["fc-1"]


def test_corrupt_line_is_reported_with_its_position(registry: RunRegistry, tmp_path: Path) -> None:
    """A damaged record must be located by line number, not silently skipped."""
    registry.add(_record("fc-1"))
    runs_file = tmp_path / ".krtr" / "runs.jsonl"
    runs_file.write_text(runs_file.read_text() + "not json\n")

    with pytest.raises(ValueError, match=r"runs\.jsonl:2"):
        registry.list_runs()
