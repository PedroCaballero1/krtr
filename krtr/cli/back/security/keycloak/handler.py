"""Defines the `krtr back security keycloak` CLI commands.

Exists to expose the local Keycloak tooling as thin commands: `test-user` creates the user
that logs in to krtr-web on this machine and shows its password once. Consumed by
`krtr/cli/back/security/__init__.py`, which registers `keycloak_app`.
"""

import logging

import httpx
import typer

from krtr.back.security.keycloak.admin_client import KeycloakAdminClient
from krtr.back.security.keycloak.config import KeycloakAdminConfig
from krtr.back.security.keycloak.local_user import delete_local_user, reset_local_user

logger = logging.getLogger(__name__)

ADMIN_TIMEOUT_SECONDS = 60  # Keycloak on Neon can be slow on its first request.

keycloak_app = typer.Typer(
    name="keycloak", help="Local Keycloak tooling (never Modal).", no_args_is_help=True
)


@keycloak_app.command(name="test-user")
def test_user(
    delete: bool = typer.Option(False, "--delete", help="Delete the test user instead."),
) -> None:
    """Creates the local test user with a new password (or deletes it) and shows how to log in.

    Exists so the README can explain the login without a password ever being committed. Needs
    the local Keycloak running (`docker compose up`) and KRTR_KEYCLOAK_ADMIN_PASSWORD in `.env`.

    Args:
        delete: When True, deletes the user instead of creating it.

    Returns:
        None.
    """
    try:
        with httpx.Client(timeout=ADMIN_TIMEOUT_SECONDS) as http_client:
            admin = KeycloakAdminClient(KeycloakAdminConfig.from_environment(), http_client)
            if delete:
                _delete(admin)
            else:
                _reset(admin)
    except (ValueError, httpx.HTTPError) as error:
        logger.error("Could not reach the local Keycloak: %s", error)
        raise typer.Exit(code=1) from error


def _reset(admin: KeycloakAdminClient) -> None:
    """Creates the test user again and logs its credentials once.

    Args:
        admin: The admin client of the local Keycloak.

    Returns:
        None.
    """
    credentials = reset_local_user(admin)
    logger.info(
        "Log in at http://localhost:8000 with user %s and password %s",
        credentials.username,
        credentials.password.get_secret_value(),
    )


def _delete(admin: KeycloakAdminClient) -> None:
    """Deletes the test user and logs whether there was one.

    Args:
        admin: The admin client of the local Keycloak.

    Returns:
        None.
    """
    if delete_local_user(admin):
        logger.info("Deleted the local test user")
