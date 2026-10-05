"""Tests KeycloakAdminConfig: the admin tooling only ever targets a Keycloak on this machine."""

import pytest
from pydantic import ValidationError

from krtr.back.security.keycloak import config as config_module
from krtr.back.security.keycloak.config import (
    KeycloakAdminConfig,
    KeycloakAdminEnvironmentVariable,
)


@pytest.mark.parametrize("origin", ["http://localhost:8080", "http://127.0.0.1:8080"])
def test_a_local_keycloak_is_accepted(origin: str) -> None:
    """docker-compose.yml publishes Keycloak on 127.0.0.1; both names reach it."""
    assert KeycloakAdminConfig(admin_password="x", origin=origin).origin == origin


@pytest.mark.parametrize(
    "origin",
    [
        "https://juan-alvarezo-2002--krtr-auth.modal.run",
        "http://localhost.evil.test:8080",
        "http://192.168.1.10:8080",
    ],
)
def test_any_other_keycloak_is_refused(origin: str) -> None:
    """The test user must never be created on Modal or on another machine."""
    with pytest.raises(ValidationError, match="Only a local Keycloak"):
        KeycloakAdminConfig(admin_password="x", origin=origin)


def test_from_environment_requires_the_admin_password(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without it the command fails with the variable's name, not with Keycloak's 401."""
    monkeypatch.setattr(config_module, "load_dotenv", lambda: None)
    monkeypatch.delenv(KeycloakAdminEnvironmentVariable.ADMIN_PASSWORD, raising=False)

    with pytest.raises(ValueError, match="KRTR_KEYCLOAK_ADMIN_PASSWORD"):
        KeycloakAdminConfig.from_environment()


def test_from_environment_reads_the_admin_password(monkeypatch: pytest.MonkeyPatch) -> None:
    """The password comes from the same variable docker-compose.yml bootstraps the admin with."""
    monkeypatch.setattr(config_module, "load_dotenv", lambda: None)
    monkeypatch.setenv(KeycloakAdminEnvironmentVariable.ADMIN_PASSWORD, "from-env")

    config = KeycloakAdminConfig.from_environment()

    assert config.admin_password.get_secret_value() == "from-env"
    assert "from-env" not in repr(config)
