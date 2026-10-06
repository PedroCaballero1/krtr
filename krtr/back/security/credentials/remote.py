"""Runs the user import on Modal, against the production Keycloak database (task 3.5, D20).

Exists because the production Keycloak is only reachable from inside Modal: the users files are
uploaded to the `krtr-credentials-import` Volume (reusing `ModalStagingVolume` of
`krtr/compute/modal/`), the `auth_import` function of the krtr-web app imports them, and the
Volume is emptied afterwards, even when the import fails, so no hash stays on Modal. The import
refuses to start while the `auth` function has containers running, unless forced: two Keycloaks
with local caches must not share the database (D20). Consumed by
`krtr/cli/back/security/credentials/handler.py`.
"""

import logging
from pathlib import Path
from typing import Protocol

from krtr.back.security.credentials.config import IMPORT_VOLUME, VOLUME_IMPORT_DIRECTORY
from krtr.back.security.keycloak.artifacts import PartialImportResult
from krtr.compute.modal.staging import StagingVolume

logger = logging.getLogger(__name__)

APP_NAME = "krtr-web"
AUTH_FUNCTION = "auth"
IMPORT_FUNCTION = "auth_import"


class AuthImportTarget(Protocol):
    """The krtr-web app's side of the import. Implemented by `ModalAuthImportTarget`."""

    def auth_is_running(self) -> bool:
        """Tells whether the `auth` function (the serving Keycloak) has running containers.

        Returns:
            bool: True if Keycloak is serving.
        """
        ...

    def run_import(self) -> PartialImportResult:
        """Runs `auth_import` on Modal and waits for it.

        Returns:
            PartialImportResult: the totals it reports.
        """
        ...


class KeycloakIsServing(Exception):
    """Raised when the import would run while the serving Keycloak is up (D20)."""


def import_on_modal(
    files: list[Path], volume: StagingVolume, target: AuthImportTarget, force: bool = False
) -> PartialImportResult:
    """Uploads the users files, runs `auth_import`, and always empties the Volume.

    Args:
        files: The users files, in order.
        volume: The import Volume.
        target: The krtr-web app on Modal.
        force: Whether to import even while `auth` is running.

    Returns:
        PartialImportResult: the totals added and skipped.

    Raises:
        KeycloakIsServing: if `auth` is running and `force` is False.
    """
    if not force and target.auth_is_running():
        raise KeycloakIsServing(
            "The auth function is running; stop it first (modal app stop krtr-web) or pass --force"
        )
    try:
        for path in files:
            volume.upload_file(path, VOLUME_IMPORT_DIRECTORY / path.name)
        logger.info("Uploaded %d users files to the %s volume", len(files), IMPORT_VOLUME)
        return target.run_import()
    finally:
        volume.remove_directory(VOLUME_IMPORT_DIRECTORY)
        logger.info("Emptied the %s volume", IMPORT_VOLUME)


class ModalAuthImportTarget:
    """The krtr-web app deployed on Modal, seen through its `auth` and `auth_import` functions.

    Exists so the Modal SDK stays behind this class; it is imported when the class is built,
    never at module level (CLAUDE.md). Consumed by the import CLI command.
    """

    def __init__(self) -> None:
        """Looks the two functions up in the deployed krtr-web app."""
        import modal

        self._auth = modal.Function.from_name(APP_NAME, AUTH_FUNCTION)
        self._import = modal.Function.from_name(APP_NAME, IMPORT_FUNCTION)

    def auth_is_running(self) -> bool:
        """Tells whether `auth` has running containers.

        Returns:
            bool: True if Keycloak is serving.
        """
        return self._auth.get_current_stats().num_total_runners > 0

    def run_import(self) -> PartialImportResult:
        """Runs `auth_import` remotely and waits for its totals.

        Returns:
            PartialImportResult: the totals it reports.
        """
        return PartialImportResult(**self._import.remote())
