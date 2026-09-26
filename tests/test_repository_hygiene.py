"""Tests that generated files (bytecode, caches) never become tracked by git.

`.gitignore` only affects untracked files: once a `.pyc` has been committed, git keeps
uploading every change to it, and Python rewrites it on each run. This test is what
keeps that from happening again.
"""

import re
import subprocess
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
GENERATED_FILE_PATTERN = re.compile(
    r"(^|/)__pycache__/|\.py[cod]$|(^|/)\.DS_Store$|(^|/)\.pytest_cache/|(^|/)\.ruff_cache/"
)


def _tracked_files() -> list[str]:
    """Lists the files git tracks, skipping the test where there is no git checkout."""
    try:
        listing = subprocess.run(
            ["git", "ls-files"],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        pytest.skip("not running inside a git checkout")
    return listing.stdout.splitlines()


def test_no_generated_files_are_tracked() -> None:
    """A tracked `.pyc` shows up in every diff, so none may be committed."""
    offenders = [path for path in _tracked_files() if GENERATED_FILE_PATTERN.search(path)]

    assert not offenders, (
        f"{len(offenders)} generated file(s) are tracked; untrack them with "
        f"`git rm -r --cached <path>` (first: {offenders[0]})"
    )


def test_gitignore_lists_the_generated_files_it_must_keep_out() -> None:
    """The ignore rules must cover bytecode, or a new `.pyc` would be committed again."""
    rules = (REPOSITORY_ROOT / ".gitignore").read_text().splitlines()

    for rule in ("__pycache__/", "*.pyc", ".pytest_cache/", ".ruff_cache/", ".venv/", ".DS_Store"):
        assert rule in rules
