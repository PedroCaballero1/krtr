"""Defines the `krtr back security audit` CLI commands (task 4.10).

Exists to expose the audit jobs as thin commands: `sync-auth-events` runs by hand the Keycloak
event sync that the `sync_auth_events` Modal cron runs every 15 minutes (task 6.5). Consumed by
`krtr/cli/back/security/__init__.py`, which registers `audit_app`.
"""

import logging

import psycopg2
import typer

from krtr.back.security.audit.keycloak_sync import sync_auth_events_from_environment

logger = logging.getLogger(__name__)

audit_app = typer.Typer(name="audit", help="Audit log jobs.", no_args_is_help=True)


@audit_app.command(name="sync-auth-events")
def sync_auth_events() -> None:
    """Copies the Keycloak login events not yet in `events`, encrypted (D3).

    Exists to run or retry the sync without waiting for the cron. Reads KRTR_AUDIT_DB_URL,
    NEON_DB_HOST and KRTR_EVENTS_KEY from the environment or `.env`.

    Args:
        None.

    Returns:
        None.
    """
    try:
        result = sync_auth_events_from_environment()
    except (ValueError, psycopg2.Error) as error:
        logger.error("Could not sync the Keycloak events: %s", error)
        raise typer.Exit(code=1) from error
    logger.info("Keycloak events: %d read, %d new", result.read, result.inserted)
