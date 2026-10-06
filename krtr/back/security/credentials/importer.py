"""Imports the generated users into Keycloak with the admin `partialImport` (task 3.5, D20).

Exists as the one import routine both places run: locally against the docker compose Keycloak,
and on Modal inside the `auth_import` function against 127.0.0.1:8081. The users of each
`krtr-users-<n>.json` are sent in chunks (Keycloak aborts a request after 300 s, its transaction
timeout, and 1,000 users take longer when the database is far away), several at a time, each a
`partialImport` that skips existing users, so a run can be repeated safely: it only adds who is
missing. (`kc.sh import --dir` cannot do this: it only imports users while creating the realm,
and the realm already exists.) Consumed by
`krtr/cli/back/security/credentials/handler.py` and `krtr/back/deploy/app.py`.
"""

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Protocol

from krtr.back.security.credentials.config import REALM
from krtr.back.security.keycloak.artifacts import PartialImportResult

logger = logging.getLogger(__name__)

_USERS_FILE = re.compile(rf"{REALM}-users-(\d+)\.json")
DEFAULT_CHUNK_SIZE = 100  # Users per partialImport; well under Keycloak's 300 s transaction.
DEFAULT_PARALLEL_REQUESTS = 1


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


def import_users(
    client: UserImportClient,
    files: list[Path],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    parallel_requests: int = DEFAULT_PARALLEL_REQUESTS,
) -> PartialImportResult:
    """Imports every file's users in chunks, several requests at a time, logging progress.

    Args:
        client: The admin client of the target Keycloak (thread-safe).
        files: The users files, in order.
        chunk_size: Users per `partialImport` request.
        parallel_requests: How many requests run at once.

    Returns:
        PartialImportResult: the totals added and skipped.

    Raises:
        ValueError: if a file is not for the krtr realm.
    """
    chunks = _chunks(files, chunk_size)
    logger.info("Importing %d files in %d requests", len(files), len(chunks))
    added = skipped = 0
    with ThreadPoolExecutor(max_workers=parallel_requests) as pool:
        for done, result in enumerate(pool.map(client.partial_import, chunks), start=1):
            added += result.added
            skipped += result.skipped
            if done % 10 == 0 or done == len(chunks):
                logger.info(
                    "%d of %d requests: %d added, %d already there",
                    done,
                    len(chunks),
                    added,
                    skipped,
                )
    logger.info("Import finished: %d users added, %d already there", added, skipped)
    return PartialImportResult(added=added, skipped=skipped)


def _chunks(files: list[Path], chunk_size: int) -> list[list[dict[str, Any]]]:
    """Reads every file and splits its users into chunks; a chunk never spans two files.

    Args:
        files: The users files, in order.
        chunk_size: Users per chunk.

    Returns:
        list[list[dict[str, Any]]]: the chunks, in file order.
    """
    chunks = []
    for path in files:
        users = _read_users(path)
        chunks += [users[start : start + chunk_size] for start in range(0, len(users), chunk_size)]
    return chunks


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
