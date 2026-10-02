"""Fakes shared by the local Keycloak tooling tests: a stand-in admin REST API on respx."""

import json

import httpx
import respx

from krtr.back.security.keycloak.config import KeycloakAdminConfig

CONFIG = KeycloakAdminConfig(admin_password="test-admin-password")
TOKEN_URL = "http://localhost:8080/realms/master/protocol/openid-connect/token"
USERS_URL = "http://localhost:8080/admin/realms/krtr/users"


class FakeKeycloakAdmin:
    """Serves the token and user endpoints of the admin API, keeping users in a dict."""

    def __init__(self, router: respx.MockRouter) -> None:
        """Registers the routes on a respx router; starts with no users."""
        self.users: dict[str, dict] = {}  # id → user representation, as POSTed.
        self.admin_logins: list[dict[str, str]] = []
        router.post(TOKEN_URL).mock(side_effect=self._token)
        router.get(USERS_URL).mock(side_effect=self._search)
        router.post(USERS_URL).mock(side_effect=self._create)
        router.delete(url__startswith=f"{USERS_URL}/").mock(side_effect=self._delete)

    def _token(self, request: httpx.Request) -> httpx.Response:
        """Accepts only the configured admin password."""
        form = dict(httpx.QueryParams(request.content.decode()))
        self.admin_logins.append(form)
        if form.get("password") != CONFIG.admin_password.get_secret_value():
            return httpx.Response(401, json={"error": "invalid_grant"})
        return httpx.Response(200, json={"access_token": "admin-token"})

    def _authorized(self, request: httpx.Request) -> bool:
        """Tells whether the request carries the admin's token."""
        return request.headers.get("Authorization") == "Bearer admin-token"

    def _search(self, request: httpx.Request) -> httpx.Response:
        """Finds users by exact username."""
        if not self._authorized(request):
            return httpx.Response(401)
        username = request.url.params["username"]
        found = [{"id": i, **u} for i, u in self.users.items() if u["username"] == username]
        return httpx.Response(200, json=found)

    def _create(self, request: httpx.Request) -> httpx.Response:
        """Creates a user, refusing a duplicate username like Keycloak (409)."""
        if not self._authorized(request):
            return httpx.Response(401)
        user = json.loads(request.content)
        if any(u["username"] == user["username"] for u in self.users.values()):
            return httpx.Response(409)
        self.users[f"id-{len(self.users) + 1}"] = user
        return httpx.Response(201)

    def _delete(self, request: httpx.Request) -> httpx.Response:
        """Deletes a user by id."""
        if not self._authorized(request):
            return httpx.Response(401)
        user_id = request.url.path.rsplit("/", 1)[-1]
        return httpx.Response(204 if self.users.pop(user_id, None) else 404)

    def password_of(self, username: str) -> str:
        """Returns the password a user was created with."""
        user = next(u for u in self.users.values() if u["username"] == username)
        return user["credentials"][0]["value"]
