"""Defines the configuration needed to authenticate against S3.

Exists so credentials are read from the environment (optionally populated by a
`.env` file) in exactly one place and validated before any network call is
made. Consumed by `krtr/database/s3/client.py` and, indirectly, by the CLI.
"""

import logging
import os
from enum import StrEnum

from dotenv import load_dotenv
from pydantic import BaseModel, SecretStr

logger = logging.getLogger(__name__)


class S3EnvironmentVariable(StrEnum):
    """The environment variables the S3 client reads its settings from.

    Centralizes the variable names so the config loader, the README and the
    tests never disagree on spelling. Consumed by `S3Config.from_environment`.
    """

    ACCESS_KEY_ID = "AWS_ACCESS_KEY_ID"
    SECRET_ACCESS_KEY = "AWS_SECRET_ACCESS_KEY"
    SESSION_TOKEN = "AWS_SESSION_TOKEN"  # Optional; only for temporary credentials.
    REGION = "AWS_DEFAULT_REGION"  # Optional; falls back to boto3's own resolution.
    ENDPOINT_URL = "AWS_ENDPOINT_URL"  # Optional; for S3-compatible services (MinIO, ...).


class S3Config(BaseModel):
    """Credentials and connection settings for an S3 client.

    Exists to give `S3Client` a validated, typed settings object instead of
    raw environment lookups. Consumed by `krtr/database/s3/client.py`.
    """

    access_key_id: str
    secret_access_key: SecretStr
    session_token: SecretStr | None = None
    region: str | None = None
    endpoint_url: str | None = None

    @classmethod
    def from_environment(cls) -> "S3Config":
        """Builds an S3Config from environment variables and any `.env` file.

        Exists so callers get credentials without reading the environment
        themselves; useful for the CLI and any script that talks to S3.

        Args:
            None.

        Returns:
            S3Config: the validated configuration.

        Raises:
            ValueError: if a required credential variable is missing or empty.
        """
        load_dotenv()
        required = (S3EnvironmentVariable.ACCESS_KEY_ID, S3EnvironmentVariable.SECRET_ACCESS_KEY)
        missing = [variable.value for variable in required if not os.environ.get(variable)]
        if missing:
            raise ValueError(f"Missing required S3 environment variables: {', '.join(missing)}")
        logger.debug("Loaded S3 credentials from the environment")
        return cls(
            access_key_id=os.environ[S3EnvironmentVariable.ACCESS_KEY_ID],
            secret_access_key=os.environ[S3EnvironmentVariable.SECRET_ACCESS_KEY],
            session_token=os.environ.get(S3EnvironmentVariable.SESSION_TOKEN) or None,
            region=os.environ.get(S3EnvironmentVariable.REGION) or None,
            endpoint_url=os.environ.get(S3EnvironmentVariable.ENDPOINT_URL) or None,
        )
