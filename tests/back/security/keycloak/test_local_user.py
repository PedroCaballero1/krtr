"""Tests the local test user: a fresh random password each time, and nothing left behind."""

import httpx
import pytest
import respx

from krtr.back.security.keycloak.admin_client import KeycloakAdminClient
from krtr.back.security.keycloak.config import KeycloakAdminConfig
from krtr.back.security.keycloak.local_user import (
    LOCAL_USERNAME,
    delete_local_user,
    reset_local_user,
)
from tests.back.security.keycloak.fakes import CONFIG, FakeKeycloakAdmin


@pytest.fixture
def keycloak() -> FakeKeycloakAdmin:
    """Serves a fake admin API for the duration of a test."""
    with respx.mock(assert_all_called=False) as router:
        yield FakeKeycloakAdmin(router)


def admin(config: KeycloakAdminConfig = CONFIG) -> KeycloakAdminClient:
    """Builds the admin client the tooling uses."""
    return KeycloakAdminClient(config, httpx.Client())


def test_reset_creates_an_enabled_user_with_a_permanent_password(
    keycloak: FakeKeycloakAdmin,
) -> None:
    """The user can log in right away, without being asked to change its password."""
    credentials = reset_local_user(admin())

    (user,) = keycloak.users.values()
    assert user["username"] == LOCAL_USERNAME == credentials.username
    assert user["enabled"] is True
    assert user["credentials"] == [
        {"type": "password", "value": credentials.password.get_secret_value(), "temporary": False}
    ]


def test_each_reset_gives_a_new_password_that_meets_the_realm_policy(
    keycloak: FakeKeycloakAdmin,
) -> None:
    """A password seen once (e.g. in a terminal) stops working after the next reset."""
    first = reset_local_user(admin()).password.get_secret_value()

    second = reset_local_user(admin()).password.get_secret_value()

    assert first != second
    assert len(second) >= 8  # realm-krtr.json: length(8).
    assert keycloak.password_of(LOCAL_USERNAME) == second
    assert len(keycloak.users) == 1


def test_the_password_is_hidden_in_the_credentials_repr(keycloak: FakeKeycloakAdmin) -> None:
    """Logging the model by mistake must not leak the password."""
    credentials = reset_local_user(admin())

    assert credentials.password.get_secret_value() not in repr(credentials)


def test_delete_removes_the_user_and_reports_it(keycloak: FakeKeycloakAdmin) -> None:
    """After testing, the shared dev Keycloak keeps no known login."""
    reset_local_user(admin())

    assert delete_local_user(admin()) is True
    assert keycloak.users == {}
    assert delete_local_user(admin()) is False


def test_a_wrong_admin_password_is_an_error_not_a_silent_skip(keycloak: FakeKeycloakAdmin) -> None:
    """Keycloak's 401 surfaces, so the CLI can say what went wrong."""
    wrong = KeycloakAdminConfig(admin_password="wrong")

    with pytest.raises(httpx.HTTPStatusError):
        reset_local_user(admin(wrong))
    assert keycloak.users == {}
