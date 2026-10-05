"""Tests OidcConfig: Keycloak's endpoints and the callback are derived, never hand-written."""

import pytest

from krtr.back.security.oidc.config import KeycloakEndpoint, OidcConfig, OidcEnvironmentVariable


def test_endpoints_and_callback_follow_the_realm_and_public_url() -> None:
    """The issuer the ID token must match and the callback Keycloak allows come from config."""
    config = OidcConfig(
        client_secret="s", auth_origin="https://auth.test", public_url="https://app.test"
    )

    assert config.issuer == "https://auth.test/realms/krtr"
    assert (
        config.endpoint(KeycloakEndpoint.TOKEN)
        == "https://auth.test/realms/krtr/protocol/openid-connect/token"
    )
    assert config.redirect_uri == "https://app.test/auth/callback"


def test_from_environment_reads_keycloak_the_public_url_and_the_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Production points the login at the Modal URLs through the environment."""
    monkeypatch.setenv(OidcEnvironmentVariable.CLIENT_SECRET, "secret-from-env")
    monkeypatch.setenv(OidcEnvironmentVariable.AUTH_ORIGIN, "https://ws--krtr-auth.modal.run")
    monkeypatch.setenv(OidcEnvironmentVariable.PUBLIC_URL, "https://ws--krtr.modal.run")

    config = OidcConfig.from_environment()

    assert config.client_secret.get_secret_value() == "secret-from-env"
    assert config.issuer == "https://ws--krtr-auth.modal.run/realms/krtr"
    assert config.redirect_uri == "https://ws--krtr.modal.run/auth/callback"


def test_a_missing_client_secret_names_its_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without the secret the code exchange cannot work, so the app must not start silently."""
    monkeypatch.delenv(OidcEnvironmentVariable.CLIENT_SECRET, raising=False)

    with pytest.raises(ValueError, match=OidcEnvironmentVariable.CLIENT_SECRET.value):
        OidcConfig.from_environment()
