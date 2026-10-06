"""Imports the generated users into Keycloak with the admin `partialImport` (task 3.5, D20).

Exists as the one import routine both places run: locally against the docker compose Keycloak,
and on Modal inside the `auth_import` function against 127.0.0.1:8081. Each
`krtr-users-<n>.json` is sent as one `partialImport` that skips existing users, so a run can be
repeated safely: it only adds who is missing. (`kc.sh import --dir` cannot do this: it only
imports users while creating the realm, and the realm already exists.) Consumed by
`krtr/cli/back/security/credentials/handler.py` and `krtr/back/deploy/app.py`.
"""

import json
import logging
import re
from pathlib import Path
from typing import Any, Protocol

from krtr.back.security.credentials.config import REALM
from krtr.back.security.keycloak.artifacts import PartialImportResult

logger = logging.getLogger(__name__)

_USERS_FILE = re.compile(rf"{REALM}-users-(\d+)\.json")


class UserImportClient(Protocol):
    """What the import needs from Keycloak. Implemented by `KeycloakAdminClient`."""

    def partial_import(self, users: list[dict[str, Any]]) -> PartialImportResult:
        """Adds users in bulk, skipping existing ones.

        Args:
            users: Keycloak user representations.

        Returns:
            PartialImportResult: how many were added and skipped.
        """
        ...


def users_files(directory: Path) -> list[Path]:
    """Lists the `krtr-users-<n>.json` files of a folder, in numeric order.

    Args:
        directory: The folder the generator wrote.

    Returns:
        list[Path]: the files, `krtr-users-2.json` before `krtr-users-10.json`.

    Raises:
        FileNotFoundError: if the folder has none.
    """
    found = [
        (int(match.group(1)), path)
        for path in directory.glob(f"{REALM}-users-*.json")
        if (match := _USERS_FILE.fullmatch(path.name))
    ]
    if not found:
        raise FileNotFoundError(f"No {REALM}-users-<n>.json files in {directory}")
    return [path for _, path in sorted(found)]


def import_users(client: UserImportClient, files: list[Path]) -> PartialImportResult:
    """Imports every file's users, one `partialImport` per file, logging progress.

    Args:
        client: The admin client of the target Keycloak.
        files: The users files, in order.

    Returns:
        PartialImportResult: the totals added and skipped.

    Raises:
        ValueError: if a file is not for the krtr realm.
    """
    added = skipped = 0
    for number, path in enumerate(files, start=1):
        result = client.partial_import(_read_users(path))
        added += result.added
        skipped += result.skipped
        logger.info(
            "Imported %s (%d of %d): %d added, %d already there",
            path.name,
            number,
            len(files),
            result.added,
            result.skipped,
        )
    logger.info("Import finished: %d users added, %d already there", added, skipped)
    return PartialImportResult(added=added, skipped=skipped)


def _read_users(path: Path) -> list[dict[str, Any]]:
    """Reads the users of one file, checking it belongs to the krtr realm.

    Args:
        path: The users file.

    Returns:
        list[dict[str, Any]]: its user representations.

    Raises:
        ValueError: if the file names another realm.
    """
    body = json.loads(path.read_text(encoding="utf-8"))
    if body.get("realm") != REALM:
        raise ValueError(f"{path.name} is for realm {body.get('realm')!r}, not {REALM!r}")
    return body["users"]
