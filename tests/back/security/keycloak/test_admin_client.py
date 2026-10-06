"""Tests KeycloakAdminClient's bulk import and its admin token renewal."""

import httpx
import pytest
import respx

from krtr.back.security.keycloak.admin_client import KeycloakAdminClient
from tests.back.security.keycloak.fakes import CONFIG, FakeKeycloakAdmin


class FakeMonotonicClock:
    """A monotonic clock the test moves forward by hand."""

    def __init__(self) -> None:
        """Starts at an arbitrary reading."""
        self.now = 100.0

    def __call__(self) -> float:
        """Returns the current reading."""
        return self.now


@pytest.fixture
def keycloak() -> FakeKeycloakAdmin:
    """Serves a stand-in admin API on respx for the duration of a test."""
    with respx.mock(assert_all_called=False) as router:
        yield FakeKeycloakAdmin(router)


def user(username: str) -> dict:
    """Builds a user as the generator writes them."""
    return {"username": username, "enabled": True, "credentials": []}


def test_partial_import_skips_existing_users(keycloak: FakeKeycloakAdmin) -> None:
    """A re-run must add only the missing users and never overwrite one (D20)."""
    admin = KeycloakAdminClient(CONFIG, httpx.Client())

    first = admin.partial_import([user("CLI-A"), user("CLI-B")])
    second = admin.partial_import([user("CLI-B"), user("CLI-C")])

    assert (first.added, first.skipped) == (2, 0)
    assert (second.added, second.skipped) == (1, 1)
    assert {body["ifResourceExists"] for body in keycloak.import_bodies} == {"SKIP"}


def test_the_admin_logs_in_again_before_the_token_expires(keycloak: FakeKeycloakAdmin) -> None:
    """A 60 s token cannot cover an import that runs for minutes."""
    clock = FakeMonotonicClock()
    admin = KeycloakAdminClient(CONFIG, httpx.Client(), clock=clock)

    admin.partial_import([user("CLI-A")])
    clock.now += 30
    admin.partial_import([user("CLI-B")])
    clock.now += 25
    admin.partial_import([user("CLI-C")])

    assert len(keycloak.admin_logins) == 2
