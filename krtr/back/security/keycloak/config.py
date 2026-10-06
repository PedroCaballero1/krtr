"""Defines how krtr reaches Keycloak: the local admin REST API, and the gateway on Modal.

Exists so the local-only tooling (the test user of `krtr back security keycloak test-user`) reads
Keycloak's location and its bootstrap admin from one place, and refuses to point at any Keycloak
that is not on this machine; and so the gateway in front of Keycloak on Modal (task 3.7, D19)
reads where Keycloak listens and the public host it serves. Consumed by
`krtr/back/security/keycloak/admin_client.py` and `krtr/back/security/keycloak/gateway.py`.
"""

import logging
import os
from enum import StrEnum
from urllib.parse import urlsplit

from dotenv import load_dotenv
from pydantic import BaseModel, SecretStr, field_validator

from krtr.back.security.headers.config import DEFAULT_AUTH_ORIGIN

logger = logging.getLogger(__name__)

ADMIN_REALM = "master"  # Where the bootstrap admin of docker-compose.yml lives.
ADMIN_CLIENT_ID = "admin-cli"  # Keycloak's built-in client for admin password logins.
ADMIN_USERNAME = "admin"  # KC_BOOTSTRAP_ADMIN_USERNAME in docker-compose.yml.
KRTR_REALM = "krtr"
LOCAL_HOSTNAMES = frozenset({"localhost", "127.0.0.1"})


class KeycloakAdminEnvironmentVariable(StrEnum):
    """The environment variables `KeycloakAdminConfig` reads.

    Exists so the variable names are not repeated as raw strings. Consumed by
    `KeycloakAdminConfig.from_environment`.
    """

    ADMIN_PASSWORD = "KRTR_KEYCLOAK_ADMIN_PASSWORD"  # Same value docker-compose.yml bootstraps.


class KeycloakAdminConfig(BaseModel):
    """Settings for the admin REST API of the Keycloak started by docker-compose.yml.

    Exists to give the admin client a validated settings object that can only describe a
    Keycloak on this machine: the test-user tooling must never create users on Modal.
    Consumed by `krtr/back/security/keycloak/admin_client.py`.
    """

    admin_password: SecretStr
    origin: str = DEFAULT_AUTH_ORIGIN
    realm: str = KRTR_REALM

    @field_validator("origin")
    @classmethod
    def _require_local_origin(cls, origin: str) -> str:
        """Rejects any Keycloak that is not on this machine.

        Exists because the test user has a known username and is meant for local testing only.

        Args:
            origin: Keycloak's origin (scheme + host[:port]).

        Returns:
            str: the origin, unchanged, when it is local.

        Raises:
            ValueError: if its hostname is not localhost or 127.0.0.1.
        """
        if urlsplit(origin).hostname not in LOCAL_HOSTNAMES:
            raise ValueError(f"Only a local Keycloak is allowed, not {origin}")
        return origin

    @classmethod
    def from_environment(cls) -> "KeycloakAdminConfig":
        """Builds the settings from the environment, loading `.env` first.

        Exists so the CLI never reads the admin password inline.

        Args:
            None.

        Returns:
            KeycloakAdminConfig: the settings for the local Keycloak.

        Raises:
            ValueError: if KRTR_KEYCLOAK_ADMIN_PASSWORD is missing or empty.
        """
        load_dotenv()
        variable = KeycloakAdminEnvironmentVariable.ADMIN_PASSWORD
        admin_password = os.environ.get(variable)
        if not admin_password:
            raise ValueError(f"Missing required environment variable: {variable.value}")
        logger.debug("Loaded the local Keycloak admin settings from the environment")
        return cls(admin_password=admin_password)


# Where Keycloak listens inside the `auth` container (KC_HTTP_HOST / KC_HTTP_PORT, task 3.1).
KEYCLOAK_INTERNAL_ORIGIN = "http://127.0.0.1:8081"


class GatewayConfig(BaseModel):
    """Settings of the gateway that publishes Keycloak on Modal (task 3.7, D19).

    Exists to give the gateway a validated, typed settings object. Consumed by
    `krtr/back/security/keycloak/gateway.py` and the `auth` function (task 6.3).
    """

    public_host: str  # The krtr-auth host, e.g. juan-alvarezo-2002--krtr-auth.modal.run.
    upstream_origin: str = KEYCLOAK_INTERNAL_ORIGIN
    timeout_seconds: float = 30.0  # A login must not hang on a stuck Keycloak.
    max_body_bytes: int = 64 * 1024  # Login and token requests are a few hundred bytes.
