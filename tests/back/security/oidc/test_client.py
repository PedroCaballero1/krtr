"""Tests KeycloakOidcClient: the login redirect, the code exchange and every ID token check."""

import base64
import hashlib
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
import respx

from krtr.back.security.oidc.artifacts import InterfaceLanguage, LoginState
from krtr.back.security.oidc.client import KeycloakOidcClient
from krtr.back.security.oidc.config import KeycloakEndpoint
from krtr.back.security.oidc.errors import LoginError, LoginFailureReason
from tests.back.security.oidc.fakes import (
    CLIENT_SECRET,
    CONFIG,
    START,
    FakeClock,
    FakeRealm,
    endpoint,
    http_client,
)


@pytest.fixture(scope="module")
def realm() -> FakeRealm:
    """One signing key for the module: generating RSA keys is slow."""
    return FakeRealm()


@pytest.fixture
def keycloak(realm: FakeRealm) -> respx.MockRouter:
    """Intercepts Keycloak's endpoints; tests set the token endpoint's answer."""
    with respx.mock(assert_all_called=False) as router:
        router.get(endpoint(KeycloakEndpoint.CERTS)).mock(
            return_value=httpx.Response(200, json=realm.jwks())
        )
        yield router


def start(clock: FakeClock | None = None) -> tuple[KeycloakOidcClient, LoginState, str]:
    """Builds a client and starts a Spanish login with it."""
    client = KeycloakOidcClient(CONFIG, http_client(), clock or FakeClock())
    login_state, url = client.start_login(InterfaceLanguage.SPANISH)
    return client, login_state, url


def answer_token_request(
    keycloak: respx.MockRouter, body: dict[str, Any], status: int = 200
) -> respx.Route:
    """Makes the token endpoint return the given body."""
    return keycloak.post(endpoint(KeycloakEndpoint.TOKEN)).mock(
        return_value=httpx.Response(status, json=body)
    )


def test_login_redirect_carries_state_nonce_pkce_and_language() -> None:
    """The browser must reach Keycloak with a fresh state, nonce and S256 challenge, in Spanish."""
    _, login_state, url = start()
    query = {key: values[0] for key, values in parse_qs(urlsplit(url).query).items()}
    expected_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(login_state.code_verifier.encode()).digest()
    )

    assert url.startswith(endpoint(KeycloakEndpoint.AUTHORIZATION) + "?")
    assert (
        query["client_id"] == "krtr-web"
        and query["redirect_uri"] == "https://krtr.test/auth/callback"
    )
    assert (query["state"], query["nonce"]) == (login_state.state, login_state.nonce)
    assert query["code_challenge"] == expected_challenge.rstrip(b"=").decode()
    assert query["code_challenge_method"] == "S256" and query["ui_locales"] == "es"
    assert "code_verifier" not in query  # The verifier only travels in the encrypted cookie.


def test_each_login_gets_fresh_secrets_valid_for_10_minutes() -> None:
    """Reusing state, nonce or verifier across logins would weaken all three protections."""
    _, first, _ = start()
    _, second, _ = start()

    assert len({first.state, second.state, first.nonce, second.nonce}) == 4
    assert first.code_verifier != second.code_verifier
    assert first.expires_at == START.replace(minute=10)


def test_complete_login_returns_the_customer_and_tokens(
    realm: FakeRealm, keycloak: respx.MockRouter
) -> None:
    """A valid callback yields the Keycloak username as customer_id, and the session's tokens."""
    client, login_state, _ = start()
    route = answer_token_request(keycloak, realm.token_response(realm.id_token(login_state.nonce)))

    identity, tokens = client.complete_login(login_state, "the-code")
    request = route.calls.last.request
    form = parse_qs(request.content.decode())

    assert (identity.customer_id, identity.subject) == ("12345678", "keycloak-user-id")
    assert tokens.access_expires_at == START.replace(minute=5)
    assert form["code"] == ["the-code"] and form["code_verifier"] == [login_state.code_verifier]
    expected_basic = base64.b64encode(f"krtr-web:{CLIENT_SECRET}".encode()).decode()
    assert request.headers["authorization"] == f"Basic {expected_basic}"


def test_an_id_token_for_another_login_is_rejected(
    realm: FakeRealm, keycloak: respx.MockRouter
) -> None:
    """A replayed ID token (nonce of another login) must not open a session."""
    client, login_state, _ = start()
    answer_token_request(keycloak, realm.token_response(realm.id_token("nonce-of-another-login")))

    with pytest.raises(LoginError) as raised:
        client.complete_login(login_state, "the-code")

    assert raised.value.reason == LoginFailureReason.NONCE_MISMATCH


@pytest.mark.parametrize(
    "claims",
    [
        {"iss": "http://evil.test/realms/krtr"},
        {"aud": "another-client"},
        {"exp": int(START.timestamp()) - 1},
    ],
    ids=["other-issuer", "other-audience", "expired"],
)
def test_id_tokens_with_wrong_claims_are_rejected(
    realm: FakeRealm, keycloak: respx.MockRouter, claims: dict[str, Any]
) -> None:
    """A token from another issuer, for another client, or expired must be refused."""
    client, login_state, _ = start()
    answer_token_request(
        keycloak, realm.token_response(realm.id_token(login_state.nonce, **claims))
    )

    with pytest.raises(LoginError) as raised:
        client.complete_login(login_state, "the-code")

    assert raised.value.reason == LoginFailureReason.INVALID_ID_TOKEN


def test_an_id_token_signed_by_another_key_is_rejected(
    realm: FakeRealm, keycloak: respx.MockRouter
) -> None:
    """A forged token with the realm's key id but another key must fail the signature check."""
    client, login_state, _ = start()
    forger = FakeRealm(key_id=realm.key.kid)
    answer_token_request(keycloak, forger.token_response(forger.id_token(login_state.nonce)))

    with pytest.raises(LoginError) as raised:
        client.complete_login(login_state, "the-code")

    assert raised.value.reason == LoginFailureReason.INVALID_ID_TOKEN


def test_a_rotated_realm_key_is_fetched_again(keycloak: respx.MockRouter) -> None:
    """After Keycloak rotates its key, the first token with the new kid must still validate."""
    old_realm, new_realm = FakeRealm("old-key"), FakeRealm("new-key")
    certs = keycloak.get(endpoint(KeycloakEndpoint.CERTS)).mock(
        side_effect=[
            httpx.Response(200, json=old_realm.jwks()),
            httpx.Response(200, json=new_realm.jwks()),
        ]
    )
    client, first_login, _ = start()
    answer_token_request(keycloak, old_realm.token_response(old_realm.id_token(first_login.nonce)))
    client.complete_login(first_login, "code-1")
    second_login, _ = client.start_login(InterfaceLanguage.PORTUGUESE)
    answer_token_request(keycloak, new_realm.token_response(new_realm.id_token(second_login.nonce)))

    identity, _ = client.complete_login(second_login, "code-2")

    assert identity.customer_id == "12345678"
    assert certs.call_count == 2


def test_a_refused_code_exchange_is_a_login_failure(keycloak: respx.MockRouter) -> None:
    """Keycloak refusing the code (reused, expired, wrong verifier) must not open a session."""
    client, login_state, _ = start()
    answer_token_request(keycloak, {"error": "invalid_grant"}, status=400)

    with pytest.raises(LoginError) as raised:
        client.complete_login(login_state, "reused-code")

    assert raised.value.reason == LoginFailureReason.TOKEN_EXCHANGE_FAILED


def test_unreachable_signing_keys_are_reported_as_such(realm: FakeRealm) -> None:
    """If the keys cannot be fetched, the failure must not be blamed on the token."""
    with respx.mock(assert_all_called=False) as router:
        router.get(endpoint(KeycloakEndpoint.CERTS)).mock(return_value=httpx.Response(503))
        client, login_state, _ = start()
        answer_token_request(router, realm.token_response(realm.id_token(login_state.nonce)))

        with pytest.raises(LoginError) as raised:
            client.complete_login(login_state, "the-code")

    assert raised.value.reason == LoginFailureReason.KEYS_UNAVAILABLE


def test_refresh_returns_tokens_with_a_new_expiry(
    realm: FakeRealm, keycloak: respx.MockRouter
) -> None:
    """A refresh keeps the session usable: new tokens, expiring 5 minutes from now."""
    clock = FakeClock()
    client, _, _ = start(clock)
    clock.advance(minutes=4)
    route = answer_token_request(keycloak, realm.token_response(realm.id_token("n")))

    tokens = client.refresh("current-refresh-token")

    assert parse_qs(route.calls.last.request.content.decode())["refresh_token"] == [
        "current-refresh-token"
    ]
    assert tokens.access_expires_at == START.replace(minute=9)


def test_end_session_logs_out_of_keycloak_and_revokes_the_refresh_token(
    realm: FakeRealm, keycloak: respx.MockRouter
) -> None:
    """Logging out of krtr must also end the Keycloak session, even if revocation fails."""
    client, login_state, _ = start()
    answer_token_request(keycloak, realm.token_response(realm.id_token(login_state.nonce)))
    _, tokens = client.complete_login(login_state, "the-code")
    logout = keycloak.post(endpoint(KeycloakEndpoint.LOGOUT)).mock(return_value=httpx.Response(204))
    revoke = keycloak.post(endpoint(KeycloakEndpoint.REVOKE)).mock(return_value=httpx.Response(503))

    client.end_session(tokens)

    assert parse_qs(logout.calls.last.request.content.decode())["refresh_token"] == [
        tokens.refresh_token
    ]
    assert parse_qs(revoke.calls.last.request.content.decode())["token"] == [tokens.refresh_token]
