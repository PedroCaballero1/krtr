"""Talks to the admin REST API of a Keycloak on this machine (or inside its container).

Exists so the tooling can find, create, delete and bulk-import users of the krtr realm without
repeating Keycloak's URLs and its admin login. Used against the local docker compose, and inside
the Modal `auth_import` function against 127.0.0.1:8081, which the gateway never exposes (D19).
Consumed by `krtr/back/security/keycloak/local_user.py` and
`krtr/back/security/credentials/importer.py`.
"""

import logging
import time
from collections.abc import Callable
from typing import Any

import httpx

from krtr.back.security.keycloak.artifacts import PartialImportResult
from krtr.back.security.keycloak.config import (
    ADMIN_CLIENT_ID,
    ADMIN_REALM,
    ADMIN_USERNAME,
    KeycloakAdminConfig,
)

logger = logging.getLogger(__name__)

TOKEN_REFRESH_MARGIN_SECONDS = 10  # Log in again this long before the admin token expires.
SKIP_EXISTING = "SKIP"  # partialImport's ifResourceExists: keep users that already exist.


class KeycloakAdminClient:
    """Manages users of one realm through Keycloak's admin REST API.

    Exists to wrap the admin login (a password grant of the bootstrap admin) and the user
    endpoints in a small interface. Consumed by `krtr/back/security/keycloak/local_user.py`.
    """

    def __init__(
        self,
        config: KeycloakAdminConfig,
        http_client: httpx.Client,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Builds the client.

        Args:
            config: Where the local Keycloak is and its admin password.
            http_client: The HTTP client to send requests with (respx intercepts it in tests).
            clock: Returns monotonic seconds, to know when the admin token expires.
        """
        self._config = config
        self._http = http_client
        self._clock = clock
        self._token: str | None = None
        self._token_expires_at = 0.0

    def find_user_id(self, username: str) -> str | None:
        """Returns the id of the realm's user with exactly that username.

        Args:
            username: The username to look for.

        Returns:
            str | None: Keycloak's user id, or None if there is no such user.
        """
        response = self._request("GET", "/users", params={"username": username, "exact": "true"})
        users = response.json()
        return users[0]["id"] if users else None

    def create_user(self, username: str, password: str) -> None:
        """Creates an enabled user with a permanent password.

        Args:
            username: The new user's username.
            password: Its password; not temporary, so no change is asked at first login.

        Returns:
            None.
        """
        credential = {"type": "password", "value": password, "temporary": False}
        user = {"username": username, "enabled": True, "credentials": [credential]}
        self._request("POST", "/users", json=user)
        logger.info("Created user %s in realm %s", username, self._config.realm)

    def delete_user(self, user_id: str) -> None:
        """Deletes a user, which also ends its sessions.

        Args:
            user_id: Keycloak's id of the user.

        Returns:
            None.
        """
        self._request("DELETE", f"/users/{user_id}")
        logger.info("Deleted user %s from realm %s", user_id, self._config.realm)

    def partial_import(self, users: list[dict[str, Any]]) -> PartialImportResult:
        """Adds users in bulk, leaving any that already exist untouched.

        Exists for the user import (task 3.5): users arrive with their password already hashed,
        and a re-run skips everyone imported before instead of failing or overwriting.

        Args:
            users: Keycloak user representations, with their credentials.

        Returns:
            PartialImportResult: how many were added and how many skipped.
        """
        body = {"ifResourceExists": SKIP_EXISTING, "users": users}
        result = self._request("POST", "/partialImport", json=body).json()
        return PartialImportResult(added=result["added"], skipped=result["skipped"])

    def _request(self, method: str, path: str, **options: object) -> httpx.Response:
        """Sends an authenticated request to the realm's admin API.

        Args:
            method: The HTTP method.
            path: The path under `/admin/realms/<realm>`.
            **options: Passed to httpx (params, json).

        Returns:
            httpx.Response: the successful response.

        Raises:
            httpx.HTTPStatusError: if Keycloak answers with an error.
        """
        url = f"{self._config.origin}/admin/realms/{self._config.realm}{path}"
        headers = {"Authorization": f"Bearer {self._admin_token()}"}
        return self._http.request(method, url, headers=headers, **options).raise_for_status()

    def _admin_token(self) -> str:
        """Returns a valid access token of the bootstrap admin, logging in again near expiry.

        A token lasts 60 s; a bulk import runs for minutes.

        Args:
            None.

        Returns:
            str: the admin's access token.

        Raises:
            httpx.HTTPStatusError: if Keycloak rejects the admin password.
        """
        now = self._clock()
        if self._token is None or now >= self._token_expires_at:
            url = f"{self._config.origin}/realms/{ADMIN_REALM}/protocol/openid-connect/token"
            form = {
                "grant_type": "password",
                "client_id": ADMIN_CLIENT_ID,
                "username": ADMIN_USERNAME,
                "password": self._config.admin_password.get_secret_value(),
            }
            granted = self._http.post(url, data=form).raise_for_status().json()
            self._token = granted["access_token"]
            lifetime = granted.get("expires_in", 60) - TOKEN_REFRESH_MARGIN_SECONDS
            self._token_expires_at = now + lifetime
        return self._token
