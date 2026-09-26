"""Tests for the Modal execution configuration and option sets."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from krtr.compute.modal.config import (
    IMAGE_SOURCE_IGNORE_PATTERNS,
    REPOSITORY_ROOT,
    ForwardedSecretVariable,
    ModalConfig,
    TaskResources,
)


def test_forwarded_secret_variables_are_an_explicit_allowlist() -> None:
    """Only the Neon connection string may leave the machine for the Modal secret."""
    assert {variable.value for variable in ForwardedSecretVariable} == {"NEON_DB_HOST"}


def test_repository_root_is_the_directory_holding_pyproject() -> None:
    """The root the run registry hangs off must be the real repository root."""
    assert (REPOSITORY_ROOT / "pyproject.toml").is_file()


def test_default_runs_file_is_git_ignored_state_outside_data() -> None:
    """Run records go in `.krtr/`, which git ignores, and never under `data/`."""
    runs_file = ModalConfig().runs_file
    assert runs_file == REPOSITORY_ROOT / ".krtr" / "runs.jsonl"
    assert REPOSITORY_ROOT / "data" not in runs_file.parents
    ignored_entries = (REPOSITORY_ROOT / ".gitignore").read_text().splitlines()
    assert ".krtr/" in ignored_entries


def test_default_region_is_unset_so_modal_chooses() -> None:
    """No region is hardcoded; it stays None until the user configures one."""
    assert ModalConfig().region is None


def test_task_resources_default_to_no_retries() -> None:
    """A failed load must not be retried automatically, or it could duplicate rows."""
    assert TaskResources().retries == 0


@pytest.mark.parametrize(
    "invalid_fields",
    [
        {"cpu": 0},
        {"cpu": -1.0},
        {"memory_mebibytes": 0},
        {"timeout_seconds": 0},
        {"retries": -1},
    ],
)
def test_task_resources_reject_non_positive_limits(invalid_fields: dict[str, float]) -> None:
    """Zero or negative resources would be rejected by Modal only after a wasted upload."""
    with pytest.raises(ValidationError):
        TaskResources(**invalid_fields)


def test_image_source_patterns_keep_sql_files_and_drop_bytecode() -> None:
    """The container needs the `.sql` files, which Modal's default filter would silently drop."""
    file_pattern_matcher = pytest.importorskip("modal.file_pattern_matcher")
    is_ignored = file_pattern_matcher.FilePatternMatcher(*IMAGE_SOURCE_IGNORE_PATTERNS)

    assert not is_ignored(Path("database/queries/products/table.sql"))
    assert not is_ignored(Path("database/neon/loader.py"))
    assert is_ignored(Path("database/neon/__pycache__/loader.cpython-314.pyc"))


def test_default_resources_are_small_and_never_include_a_gpu() -> None:
    """Runs cost money by the second; a load waits on Neon and needs neither GPU nor a full core."""
    resources = TaskResources()

    assert (resources.cpu, resources.memory_mebibytes) == (0.25, 512)
    assert "gpu" not in TaskResources.model_fields
