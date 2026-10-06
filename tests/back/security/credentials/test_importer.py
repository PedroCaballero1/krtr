"""Tests the user import: every file, in order, idempotent, and only for the krtr realm."""

import json
from pathlib import Path
from typing import Any

import pytest

from krtr.back.security.credentials.importer import import_users, users_files
from krtr.back.security.keycloak.artifacts import PartialImportResult


class FakeImportClient:
    """Stands in for KeycloakAdminClient: keeps usernames, skipping those it already has."""

    def __init__(self) -> None:
        """Starts with no users."""
        self.usernames: list[str] = []

    def partial_import(self, users: list[dict[str, Any]]) -> PartialImportResult:
        """Adds the users it does not have yet."""
        new = [user["username"] for user in users if user["username"] not in self.usernames]
        self.usernames.extend(new)
        return PartialImportResult(added=len(new), skipped=len(users) - len(new))


def write_users_file(
    directory: Path, index: int, usernames: list[str], realm: str = "krtr"
) -> Path:
    """Writes one users file as the generator does."""
    path = directory / f"krtr-users-{index}.json"
    users = [{"username": name, "enabled": True, "credentials": []} for name in usernames]
    path.write_text(json.dumps({"realm": realm, "users": users}))
    return path


def test_files_are_listed_in_numeric_order(tmp_path: Path) -> None:
    """krtr-users-10 comes after krtr-users-2, and unrelated files are ignored."""
    for index in (10, 2, 0):
        write_users_file(tmp_path, index, [f"CLI-{index}"])
    (tmp_path / "manifest.json").write_text("{}")

    assert [path.name for path in users_files(tmp_path)] == [
        "krtr-users-0.json",
        "krtr-users-2.json",
        "krtr-users-10.json",
    ]


def test_a_folder_without_users_files_is_an_error(tmp_path: Path) -> None:
    """Importing nothing silently would look like success."""
    with pytest.raises(FileNotFoundError):
        users_files(tmp_path)


def test_every_user_of_every_file_is_imported(tmp_path: Path) -> None:
    """The totals add up across files."""
    write_users_file(tmp_path, 0, ["CLI-A", "CLI-B"])
    write_users_file(tmp_path, 1, ["CLI-C"])
    client = FakeImportClient()

    result = import_users(client, users_files(tmp_path))

    assert client.usernames == ["CLI-A", "CLI-B", "CLI-C"]
    assert (result.added, result.skipped) == (3, 0)


def test_a_second_run_adds_nothing(tmp_path: Path) -> None:
    """D20: the import can be repeated after a failure without duplicating anyone."""
    write_users_file(tmp_path, 0, ["CLI-A", "CLI-B"])
    client = FakeImportClient()
    import_users(client, users_files(tmp_path))

    result = import_users(client, users_files(tmp_path))

    assert (result.added, result.skipped) == (0, 2)


def test_a_file_for_another_realm_is_rejected(tmp_path: Path) -> None:
    """Users of another realm must never land in krtr (or in master)."""
    write_users_file(tmp_path, 0, ["admin2"], realm="master")

    with pytest.raises(ValueError, match="master"):
        import_users(FakeImportClient(), users_files(tmp_path))
