"""Defines the configuration needed to connect to the Neon Postgres database.

Exists so the connection string is read from the environment (optionally
populated by a `.env` file) in exactly one place and validated before any
connection is opened. Consumed by `krtr/database/neon/client.py`.
"""

import logging
import os
from enum import StrEnum

from dotenv import load_dotenv
from pydantic import BaseModel, SecretStr

logger = logging.getLogger(__name__)


class NeonEnvironmentVariable(StrEnum):
    """The environment variables the Neon client reads its settings from.

    Centralizes the variable names so the config loader, the README and the
    tests never disagree on spelling. Consumed by `NeonConfig.from_environment`.
    """

    CONNECTION_STRING = "NEON_DB_HOST"  # Full postgresql:// URL, not just a hostname.
    POOL_MIN_SIZE = "NEON_POOL_MIN_SIZE"  # Optional; defaults to NeonConfig.pool_min_size.
    POOL_MAX_SIZE = "NEON_POOL_MAX_SIZE"  # Optional; defaults to NeonConfig.pool_max_size.


class NeonConfig(BaseModel):
    """Connection settings for the Neon Postgres database.

    Exists to give `NeonClient` a validated, typed settings object instead of
    a raw environment lookup. Consumed by `krtr/database/neon/client.py`.
    """

    connection_string: SecretStr
    pool_min_size: int = 1
    pool_max_size: int = 10  # Cloud Run runs krtr-web with a single instance (D8) serving <20
    # concurrent jurors; 10 pooled connections comfortably covers that load.

    @classmethod
    def from_environment(cls) -> "NeonConfig":
        """Builds a NeonConfig from the environment and any `.env` file.

        Exists so callers get the connection string without reading the
        environment themselves; useful for the CLI and any script that talks
        to Neon.

        Args:
            None.

        Returns:
            NeonConfig: the validated configuration.

        Raises:
            ValueError: if `NEON_DB_HOST` is missing or empty.
        """
        load_dotenv()
        connection_string = os.environ.get(NeonEnvironmentVariable.CONNECTION_STRING)
        if not connection_string:
            raise ValueError(
                "Missing required environment variable: "
                f"{NeonEnvironmentVariable.CONNECTION_STRING.value}"
            )
        logger.debug("Loaded Neon connection string from the environment")
        pool_settings = {}
        if pool_min_size := os.environ.get(NeonEnvironmentVariable.POOL_MIN_SIZE):
            pool_settings["pool_min_size"] = int(pool_min_size)
        if pool_max_size := os.environ.get(NeonEnvironmentVariable.POOL_MAX_SIZE):
            pool_settings["pool_max_size"] = int(pool_max_size)
        return cls(connection_string=connection_string, **pool_settings)
