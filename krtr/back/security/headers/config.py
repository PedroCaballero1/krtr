"""Defines configuration for krtr-web's security-headers middleware.

Exists so the one value the headers depend on beyond static policy text —
Keycloak's origin, needed in the CSP's `form-action` — is read from the
environment in one place. Consumed by `krtr/back/security/headers/middleware.py`.
"""

import logging
import os
from enum import StrEnum

from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Local Keycloak, as docker-compose (task 3.1) will expose it. Overridden via
# KRTR_AUTH_ORIGIN with the krtr-auth URL on Modal (D11).
DEFAULT_AUTH_ORIGIN = "http://localhost:8080"


class HeadersEnvironmentVariable(StrEnum):
    """The environment variable `HeadersConfig` reads from the environment.

    Centralizes the variable name so the config loader, the README and the
    tests never disagree on spelling. Consumed by `HeadersConfig.from_environment`.
    """

    AUTH_ORIGIN = "KRTR_AUTH_ORIGIN"


class HeadersConfig(BaseModel):
    """Configuration for the security-headers middleware.

    Exists to give the middleware a validated, typed settings object instead
    of reading the environment inline. Consumed by
    `krtr/back/security/headers/middleware.py`.
    """

    auth_origin: str = DEFAULT_AUTH_ORIGIN  # Keycloak's origin (scheme + host[:port]),
    # allowed as a CSP form-action target so the OIDC login form can submit to it.

    @classmethod
    def from_environment(cls) -> "HeadersConfig":
        """Builds a HeadersConfig from the environment, defaulting to local Keycloak.

        Args:
            None.

        Returns:
            HeadersConfig: the resolved configuration.
        """
        settings: dict[str, str] = {}
        if auth_origin := os.environ.get(HeadersEnvironmentVariable.AUTH_ORIGIN):
            settings["auth_origin"] = auth_origin
        logger.debug("Loaded security-headers configuration from the environment: %s", settings)
        return cls(**settings)
