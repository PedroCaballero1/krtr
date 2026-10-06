"""Tests the Modal secrets of krtr-web (task 6.1): each gets only what its functions need."""

import pytest

from krtr.back.deploy.config import DeploySecret
from krtr.back.deploy.secrets import SourceVariable, build_secret_values

SOURCE = {
    SourceVariable.NEON_ADMIN_URL.value: (
        "postgresql://neondb_owner:owner-pw@ep-dawn-forest-b53h756c-pooler.c-7.us-east-2"
        ".aws.neon.tech/neondb?sslmode=require"
    ),
    SourceVariable.APP_PASSWORD.value: "app p@ss/word",
    SourceVariable.KEYCLOAK_PASSWORD.value: "kc-pw",
    SourceVariable.TOKENS_KEY.value: "tokens-key",
    SourceVariable.EVENTS_KEY.value: "events-key",
    SourceVariable.MESSAGES_KEY.value: "messages-key",
    SourceVariable.PROD_CLIENT_SECRET.value: "client-secret",
    SourceVariable.PROD_ADMIN_PASSWORD.value: "admin-pw",
}


def test_the_app_connects_as_krtr_app_never_as_the_owner() -> None:
    """The served app must not hold the owner's credentials (least privilege, 1.3)."""
    url = build_secret_values(SOURCE)[DeploySecret.WEB]["NEON_DB_HOST"]

    assert url.startswith(
        "postgresql://krtr_app:app%20p%40ss%2Fword@ep-dawn-forest-b53h756c-pooler"
    )
    assert "owner" not in url
    assert url.endswith("/neondb?sslmode=require&channel_binding=require")


def test_keycloak_uses_the_direct_host_and_its_own_database() -> None:
    """Keycloak needs a direct (non-pooled) connection to its `keycloak` database (1.3)."""
    auth = build_secret_values(SOURCE)[DeploySecret.AUTH]

    assert auth["KC_DB_URL"] == (
        "jdbc:postgresql://ep-dawn-forest-b53h756c.c-7.us-east-2.aws.neon.tech/keycloak"
        "?sslmode=require"
    )
    assert auth["KC_DB_USERNAME"] == "krtr_keycloak"


def test_each_secret_gets_only_its_variables() -> None:
    """Nothing reaches a function that does not need it; the jobs never see login secrets."""
    values = build_secret_values(SOURCE)

    assert set(values[DeploySecret.JOBS]) == {
        "NEON_DB_HOST",
        "KRTR_EVENTS_KEY",
        "KRTR_MESSAGES_KEY",
    }
    assert "KC_DB_PASSWORD" not in values[DeploySecret.WEB]
    assert "KRTR_TOKENS_KEY" not in values[DeploySecret.AUTH]
    assert values[DeploySecret.WEB]["KRTR_WEB_OIDC_CLIENT_SECRET"] == (
        values[DeploySecret.AUTH]["KRTR_WEB_OIDC_CLIENT_SECRET"]
    )


def test_the_web_points_at_the_modal_urls() -> None:
    """The callback and the CSRF origin must be the public krtr URL (D11)."""
    web = build_secret_values(SOURCE)[DeploySecret.WEB]

    assert web["KRTR_PUBLIC_URL"] == "https://juan-alvarezo-2002--krtr.modal.run"
    assert web["KRTR_AUTH_ORIGIN"] == "https://juan-alvarezo-2002--krtr-auth.modal.run"


def test_a_missing_variable_fails_naming_it() -> None:
    """A half-built secret would make the app fail at start; stop before pushing anything."""
    source = {**SOURCE, SourceVariable.MESSAGES_KEY.value: ""}

    with pytest.raises(ValueError, match="KRTR_MESSAGES_KEY"):
        build_secret_values(source)
