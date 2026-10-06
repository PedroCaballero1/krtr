"""Defines the configuration of the Keycloak event sync (task 4.10, D3).

Exists so the read-only connection to Keycloak's database and the overlap the sync re-reads are
declared and validated in one place. In production Modal injects the connection string from the
`krtr-jobs` secret (task 6.1); locally it comes from `.env`. Consumed by
`krtr/back/security/audit/keycloak_sync.py`.
"""

import logging
import os
from datetime import timedelta
from enum import StrEnum

from dotenv import load_dotenv
from pydantic import BaseModel, SecretStr

logger = logging.getLogger(__name__)

# Keycloak can commit an event a little after its timestamp, so each run re-reads this much
# before the latest copied event; the inserts skip what is already there.
SYNC_OVERLAP = timedelta(minutes=15)


class AuditEnvironmentVariable(StrEnum):
    """The environment variables the Keycloak event sync reads its settings from.

    Centralizes the variable names so the config loader, the Modal secrets of
    `krtr/back/deploy/secrets.py` and the tests never disagree on spelling. Consumed by
    `AuthEventSyncConfig.from_environment`.
    """

    # postgresql:// URL of the `keycloak` database as krtr_audit_reader, which can only read
    # `event_entity`.
    KEYCLOAK_EVENTS_URL = "KRTR_AUDIT_DB_URL"


class AuthEventSyncConfig(BaseModel):
    """Configuration of the Keycloak event sync.

    Exists to give the sync a validated connection string instead of a raw environment lookup.
    The `events` side reuses the app's own Neon configuration (`NEON_DB_HOST`) and events key.
    Consumed by `krtr/back/security/audit/keycloak_sync.py`.
    """

    keycloak_events_connection_string: SecretStr
    overlap: timedelta = SYNC_OVERLAP

    @classmethod
    def from_environment(cls) -> "AuthEventSyncConfig":
        """Builds the configuration from the environment and any `.env` file.

        Exists so the CLI and the Modal cron read the connection string the same way.

        Args:
            None.

        Returns:
            AuthEventSyncConfig: the validated configuration.

        Raises:
            ValueError: if `KRTR_AUDIT_DB_URL` is missing or empty.
        """
        load_dotenv()
        connection_string = os.environ.get(AuditEnvironmentVariable.KEYCLOAK_EVENTS_URL)
        if not connection_string:
            raise ValueError(
                "Missing required environment variable: "
                f"{AuditEnvironmentVariable.KEYCLOAK_EVENTS_URL.value}"
            )
        logger.debug("Loaded the Keycloak events connection string from the environment")
        return cls(keycloak_events_connection_string=connection_string)
