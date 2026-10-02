"""Tests `krtr back security keycloak test-user`: it shows a working password once, or deletes."""

import pytest
import respx
from typer.testing import CliRunner

from krtr.back.security.keycloak import config as config_module
from krtr.back.security.keycloak.config import KeycloakAdminEnvironmentVariable
from krtr.back.security.keycloak.local_user import LOCAL_USERNAME
from krtr.cli.main import app
from tests.back.security.keycloak.fakes import CONFIG, FakeKeycloakAdmin

runner = CliRunner()


@pytest.fixture
def keycloak(monkeypatch: pytest.MonkeyPatch) -> FakeKeycloakAdmin:
    """Serves a fake admin API and gives the command the matching admin password."""
    monkeypatch.setattr(config_module, "load_dotenv", lambda: None)
    monkeypatch.setenv(
        KeycloakAdminEnvironmentVariable.ADMIN_PASSWORD, CONFIG.admin_password.get_secret_value()
    )
    with respx.mock(assert_all_called=False) as router:
        yield FakeKeycloakAdmin(router)


def test_test_user_shows_the_password_keycloak_was_given(keycloak: FakeKeycloakAdmin) -> None:
    """The password shown is the one that logs in, together with where to log in."""
    result = runner.invoke(app, ["back", "security", "keycloak", "test-user"])

    assert result.exit_code == 0, result.output
    password = keycloak.password_of(LOCAL_USERNAME)
    assert (
        f"http://localhost:8000 with user {LOCAL_USERNAME} and password {password}" in result.output
    )


def test_test_user_delete_leaves_no_user(keycloak: FakeKeycloakAdmin) -> None:
    """`--delete` removes the user created before."""
    runner.invoke(app, ["back", "security", "keycloak", "test-user"])

    result = runner.invoke(app, ["back", "security", "keycloak", "test-user", "--delete"])

    assert result.exit_code == 0, result.output
    assert keycloak.users == {}


def test_test_user_fails_clearly_without_the_admin_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing .env variable exits with 1 and names it."""
    monkeypatch.setattr(config_module, "load_dotenv", lambda: None)
    monkeypatch.delenv(KeycloakAdminEnvironmentVariable.ADMIN_PASSWORD, raising=False)

    result = runner.invoke(app, ["back", "security", "keycloak", "test-user"])

    assert result.exit_code == 1
    assert "KRTR_KEYCLOAK_ADMIN_PASSWORD" in result.output
