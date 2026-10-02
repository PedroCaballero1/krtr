"""Fakes shared by the OIDC and auth tests: a fixed clock and a stand-in Keycloak realm."""

import time
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from joserfc import jwt
from joserfc.jwk import RSAKey

from krtr.back.security.oidc.config import KeycloakEndpoint, OidcConfig

START = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)
CLIENT_SECRET = "test-client-secret"
CONFIG = OidcConfig(
    client_secret=CLIENT_SECRET, auth_origin="http://keycloak.test", public_url="https://krtr.test"
)


class FakeClock:
    """A clock tests move forward by hand."""

    def __init__(self, now: datetime = START) -> None:
        """Starts at the given time."""
        self.now = now

    def __call__(self) -> datetime:
        """Returns the current fake time."""
        return self.now

    def advance(self, **delta: float) -> None:
        """Moves the clock forward, e.g. advance(minutes=5)."""
        self.now += timedelta(**delta)


class FakeRealm:
    """Signs ID tokens like the krtr realm and serves its public keys and token responses."""

    def __init__(self, key_id: str = "realm-key") -> None:
        """Creates the realm's RSA signing key."""
        self.key = RSAKey.generate_key(2048, parameters={"kid": key_id})

    def jwks(self) -> dict[str, Any]:
        """Returns the realm's public keys, as GET .../certs does."""
        return {"keys": [self.key.as_dict(private=False)]}

    def id_token(self, nonce: str, now: datetime = START, **overrides: Any) -> str:
        """Issues an ID token for customer 12345678; overrides replace any claim."""
        issued_at = int(now.timestamp())
        claims = {
            "iss": CONFIG.issuer,
            "aud": CONFIG.client_id,
            "sub": "keycloak-user-id",
            "preferred_username": "12345678",
            "iat": issued_at,
            "exp": issued_at + 300,
            "nonce": nonce,
            **overrides,
        }
        return jwt.encode({"alg": "RS256", "kid": self.key.kid}, claims, self.key)

    def token_response(self, id_token: str, expires_in: int = 300) -> dict[str, Any]:
        """Returns a token endpoint body carrying the given ID token."""
        return {
            "access_token": f"access-{time.monotonic_ns()}",
            "refresh_token": f"refresh-{time.monotonic_ns()}",
            "id_token": id_token,
            "expires_in": expires_in,
            "token_type": "Bearer",
        }


def endpoint(kind: KeycloakEndpoint) -> str:
    """Returns the fake realm's URL for one OIDC endpoint."""
    return CONFIG.endpoint(kind)


def http_client() -> httpx.Client:
    """Returns the HTTP client the OIDC client uses; respx intercepts its requests."""
    return httpx.Client()
