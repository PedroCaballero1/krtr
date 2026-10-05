"""Defines the configuration of krtr-web's OIDC login against Keycloak (task 4.3).

Exists so Keycloak's location, the realm, the client and its secret, and the app's public URL
are read from the environment in one place, and every Keycloak endpoint is derived from them
instead of being written out by hand. Consumed by `krtr/back/security/oidc/client.py` and
`krtr/back/web/routers/auth.py`.
"""

import logging
import os
from datetime import timedelta
from enum import StrEnum

from pydantic import BaseModel, SecretStr

from krtr.back.security.headers.config import DEFAULT_AUTH_ORIGIN, HeadersEnvironmentVariable

logger = logging.getLogger(__name__)

# `krtr back web serve` on this machine; production sets KRTR_PUBLIC_URL to the Modal URL.
DEFAULT_PUBLIC_URL = "http://localhost:8000"

# The temporary login cookie of D22: `__Host-` so no other *.modal.run app can overwrite it.
LOGIN_COOKIE_NAME = "__Host-krtr_oidc"
LOGIN_COOKIE_LIFETIME = timedelta(minutes=10)

CALLBACK_PATH = "/auth/callback"
LOGIN_SCOPE = "openid"


class OidcEnvironmentVariable(StrEnum):
    """The environment variables `OidcConfig` reads.

    Keycloak's origin is the headers' KRTR_AUTH_ORIGIN, so the CSP's form-action and the login
    always point at the same Keycloak. Consumed by `OidcConfig.from_environment`.
    """

    AUTH_ORIGIN = HeadersEnvironmentVariable.AUTH_ORIGIN.value
    PUBLIC_URL = "KRTR_PUBLIC_URL"  # Where users reach krtr-web, e.g. the Modal URL.
    CLIENT_SECRET = "KRTR_WEB_OIDC_CLIENT_SECRET"  # Same value realm-krtr.json imports.


class KeycloakEndpoint(StrEnum):
    """The OIDC endpoints of a Keycloak realm, by their path under `protocol/openid-connect/`.

    Exists so endpoints are derived from the issuer instead of copied as literal URLs.
    Consumed by `OidcConfig.endpoint`.
    """

    AUTHORIZATION = "auth"
    TOKEN = "token"
    CERTS = "certs"  # The realm's public signing keys (JWKS).
    LOGOUT = "logout"
    REVOKE = "revoke"


class OidcConfig(BaseModel):
    """Settings of the OIDC Authorization Code + PKCE login against the krtr realm.

    Exists to give the OIDC client a validated, typed settings object instead of reading the
    environment inline. Consumed by `krtr/back/security/oidc/client.py`.
    """

    client_secret: SecretStr
    auth_origin: str = DEFAULT_AUTH_ORIGIN  # Keycloak's origin (scheme + host[:port]).
    public_url: str = DEFAULT_PUBLIC_URL
    realm: str = "krtr"
    client_id: str = "krtr-web"

    @property
    def issuer(self) -> str:
        """Returns the realm's issuer, which every ID token's `iss` must match.

        Returns:
            str: `<auth_origin>/realms/<realm>`.
        """
        return f"{self.auth_origin}/realms/{self.realm}"

    @property
    def redirect_uri(self) -> str:
        """Returns the callback URL registered for krtr-web in realm-krtr.json.

        Returns:
            str: `<public_url>/auth/callback`.
        """
        return f"{self.public_url}{CALLBACK_PATH}"

    def endpoint(self, endpoint: KeycloakEndpoint) -> str:
        """Returns the URL of one of the realm's OIDC endpoints.

        Args:
            endpoint: Which endpoint to build.

        Returns:
            str: the endpoint's absolute URL.
        """
        return f"{self.issuer}/protocol/openid-connect/{endpoint.value}"

    @classmethod
    def from_environment(cls) -> "OidcConfig":
        """Builds an OidcConfig from the environment.

        Args:
            None.

        Returns:
            OidcConfig: the resolved configuration.

        Raises:
            ValueError: if KRTR_WEB_OIDC_CLIENT_SECRET is missing or empty.
        """
        secret_variable = OidcEnvironmentVariable.CLIENT_SECRET
        client_secret = os.environ.get(secret_variable)
        if not client_secret:
            raise ValueError(f"Missing required environment variable: {secret_variable.value}")
        settings = {
            field: value
            for field, variable in (
                ("auth_origin", OidcEnvironmentVariable.AUTH_ORIGIN),
                ("public_url", OidcEnvironmentVariable.PUBLIC_URL),
            )
            if (value := os.environ.get(variable))
        }
        logger.debug("Loaded OIDC configuration from the environment: %s", settings)
        return cls(client_secret=client_secret, **settings)
