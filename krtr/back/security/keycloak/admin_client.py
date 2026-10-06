"""Talks to the admin REST API of the local Keycloak.

Exists so the local tooling can find, create and delete users of the krtr realm without
repeating Keycloak's URLs and its admin login. Consumed by
`krtr/back/security/keycloak/local_user.py`.
"""

import logging

import httpx

from krtr.back.security.keycloak.config import (
    ADMIN_CLIENT_ID,
    ADMIN_REALM,
    ADMIN_USERNAME,
    KeycloakAdminConfig,
)

logger = logging.getLogger(__name__)


class KeycloakAdminClient:
    """Manages users of one realm through Keycloak's admin REST API.

    Exists to wrap the admin login (a password grant of the bootstrap admin) and the user
    endpoints in a small interface. Consumed by `krtr/back/security/keycloak/local_user.py`.
    """

    def __init__(self, config: KeycloakAdminConfig, http_client: httpx.Client) -> None:
        """Builds the client.

        Args:
            config: Where the local Keycloak is and its admin password.
            http_client: The HTTP client to send requests with (respx intercepts it in tests).
        """
        self._config = config
        self._http = http_client
        self._token: str | None = None

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
        """Logs the bootstrap admin in once and returns its access token.

        A token lasts 60 s, longer than any command of this tooling.

        Args:
            None.

        Returns:
            str: the admin's access token.

        Raises:
            httpx.HTTPStatusError: if Keycloak rejects the admin password.
        """
        if self._token is None:
            url = f"{self._config.origin}/realms/{ADMIN_REALM}/protocol/openid-connect/token"
            form = {
                "grant_type": "password",
                "client_id": ADMIN_CLIENT_ID,
                "username": ADMIN_USERNAME,
                "password": self._config.admin_password.get_secret_value(),
            }
            self._token = self._http.post(url, data=form).raise_for_status().json()["access_token"]
        return self._token
