"""Implements krtr-web's OIDC Authorization Code + PKCE login against Keycloak (task 4.3).

Exists so the backend-for-frontend talks OIDC in one place: it builds the login redirect,
exchanges the code (with the client secret and the PKCE verifier), validates the ID token's
signature, issuer, audience, expiry and nonce, refreshes tokens, and ends the Keycloak session.
The browser never sees a token. Uses Authlib for PKCE and joserfc (Authlib's successor for JOSE)
for the ID token. Consumed by `krtr/back/web/routers/auth.py` and the session service.
"""

import logging
import secrets
from datetime import timedelta
from urllib.parse import urlencode

import httpx
from authlib.oauth2.rfc7636 import create_s256_code_challenge
from joserfc import jws, jwt
from joserfc.errors import InvalidClaimError, JoseError
from joserfc.jwk import KeySet

from krtr.back.security.clock import Clock, utc_now
from krtr.back.security.oidc.artifacts import (
    InterfaceLanguage,
    LoginIdentity,
    LoginState,
    OidcTokens,
)
from krtr.back.security.oidc.config import (
    LOGIN_COOKIE_LIFETIME,
    LOGIN_SCOPE,
    KeycloakEndpoint,
    OidcConfig,
)
from krtr.back.security.oidc.errors import LoginError, LoginFailureReason

logger = logging.getLogger(__name__)

ID_TOKEN_ALGORITHMS = ["RS256"]  # Keycloak's default; refusing others blocks algorithm swaps.
PKCE_METHOD = "S256"


class KeycloakOidcClient:
    """The OIDC relying party of krtr-web, against the krtr realm.

    Exists so the auth router and the session service never build OIDC requests or check
    tokens themselves. Consumed by `krtr/back/web/routers/auth.py` (login, callback, logout)
    and `krtr/back/security/sessions/service.py` (token refresh).
    """

    def __init__(self, config: OidcConfig, http: httpx.Client, clock: Clock = utc_now) -> None:
        """Builds a client for one Keycloak realm.

        Args:
            config: The realm, client, secret and URLs to use.
            http: The HTTP client for Keycloak's endpoints (a fake transport in tests).
            clock: Where the current time comes from (a fake clock in tests).
        """
        self._config = config
        self._http = http
        self._clock = clock
        self._key_set: KeySet | None = None

    def start_login(self, language: InterfaceLanguage) -> tuple[LoginState, str]:
        """Creates a new login: fresh state, nonce and PKCE verifier, and Keycloak's login URL.

        Args:
            language: The interface language, passed to Keycloak as `ui_locales`.

        Returns:
            tuple[LoginState, str]: what the login cookie must carry, and where to redirect.
        """
        login_state = LoginState(
            state=secrets.token_urlsafe(32),
            nonce=secrets.token_urlsafe(32),
            code_verifier=secrets.token_urlsafe(64),
            language=language,
            expires_at=self._clock() + LOGIN_COOKIE_LIFETIME,
        )
        return login_state, self._authorization_url(login_state)

    def complete_login(
        self, login_state: LoginState, code: str
    ) -> tuple[LoginIdentity, OidcTokens]:
        """Exchanges the callback's code and validates the ID token it brings.

        Args:
            login_state: The login this browser started, from its cookie.
            code: The authorization code from the callback.

        Returns:
            tuple[LoginIdentity, OidcTokens]: who logged in, and the session's tokens.

        Raises:
            LoginError: if the exchange fails or the ID token is not valid for this login.
        """
        payload = self._token_request(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self._config.redirect_uri,
                "code_verifier": login_state.code_verifier,
            },
            LoginFailureReason.TOKEN_EXCHANGE_FAILED,
        )
        tokens = self._tokens_from(payload)
        return self._validate_id_token(tokens.id_token, login_state.nonce), tokens

    def refresh(self, refresh_token: str) -> OidcTokens:
        """Exchanges a refresh token for new tokens, keeping the Keycloak session alive.

        Args:
            refresh_token: The session's current refresh token.

        Returns:
            OidcTokens: the new tokens.

        Raises:
            LoginError: if Keycloak refuses the refresh (e.g. its session ended).
        """
        payload = self._token_request(
            {"grant_type": "refresh_token", "refresh_token": refresh_token},
            LoginFailureReason.TOKEN_EXCHANGE_FAILED,
        )
        return self._tokens_from(payload)

    def end_session(self, tokens: OidcTokens) -> None:
        """Ends the user's Keycloak session and revokes its refresh token, best effort.

        Exists so logging out of krtr also logs out of Keycloak, without a browser redirect
        (POST /auth/logout answers 204). A failure is logged, never raised: the krtr session
        is revoked either way.

        Args:
            tokens: The session's tokens.

        Returns:
            None.
        """
        refresh_form = {"refresh_token": tokens.refresh_token}
        revoke_form = {"token": tokens.refresh_token, "token_type_hint": "refresh_token"}
        for endpoint, form in (
            (KeycloakEndpoint.LOGOUT, refresh_form),
            (KeycloakEndpoint.REVOKE, revoke_form),
        ):
            try:
                self._post(endpoint, form).raise_for_status()
            except httpx.HTTPError as error:
                logger.warning("Keycloak %s failed during logout: %s", endpoint.value, error)

    def _authorization_url(self, login_state: LoginState) -> str:
        """Builds Keycloak's authorization URL for a login.

        Args:
            login_state: The login's state, nonce, verifier and language.

        Returns:
            str: the URL to redirect the browser to.
        """
        query = {
            "client_id": self._config.client_id,
            "response_type": "code",
            "scope": LOGIN_SCOPE,
            "redirect_uri": self._config.redirect_uri,
            "state": login_state.state,
            "nonce": login_state.nonce,
            "code_challenge": create_s256_code_challenge(login_state.code_verifier),
            "code_challenge_method": PKCE_METHOD,
            "ui_locales": login_state.language.value,
        }
        return f"{self._config.endpoint(KeycloakEndpoint.AUTHORIZATION)}?{urlencode(query)}"

    def _token_request(self, form: dict[str, str], failure: LoginFailureReason) -> dict:
        """Calls the token endpoint and returns its JSON, or fails with the given reason.

        Args:
            form: The grant's form fields; the client authenticates with HTTP Basic.
            failure: The reason to raise if Keycloak refuses.

        Returns:
            dict: the token response.

        Raises:
            LoginError: if the request fails or Keycloak answers with an error.
        """
        try:
            response = self._post(KeycloakEndpoint.TOKEN, form)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as error:
            logger.warning("Keycloak token request failed: %s", error)
            raise LoginError(failure) from error

    def _post(self, endpoint: KeycloakEndpoint, form: dict[str, str]) -> httpx.Response:
        """POSTs a form to one of the realm's endpoints as the krtr-web client.

        Args:
            endpoint: Which endpoint to call.
            form: The form fields.

        Returns:
            httpx.Response: Keycloak's response.
        """
        credentials = (self._config.client_id, self._config.client_secret.get_secret_value())
        return self._http.post(self._config.endpoint(endpoint), data=form, auth=credentials)

    def _tokens_from(self, payload: dict) -> OidcTokens:
        """Reads the tokens and the access token's expiry from a token response.

        Args:
            payload: The token endpoint's JSON.

        Returns:
            OidcTokens: the tokens, with an absolute access-token expiry.
        """
        return OidcTokens(
            access_token=payload["access_token"],
            refresh_token=payload["refresh_token"],
            id_token=payload["id_token"],
            access_expires_at=self._clock() + timedelta(seconds=int(payload["expires_in"])),
        )

    def _validate_id_token(self, id_token: str, nonce: str) -> LoginIdentity:
        """Checks the ID token's signature and claims, and reads who logged in.

        Args:
            id_token: The ID token from the token response.
            nonce: The nonce this login sent, which the token must echo.

        Returns:
            LoginIdentity: the customer and Keycloak user id.

        Raises:
            LoginError: NONCE_MISMATCH if the nonce differs; KEYS_UNAVAILABLE if Keycloak's
                keys cannot be fetched; INVALID_ID_TOKEN for any other failure (signature,
                issuer, audience, expiry).
        """
        try:
            keys = self._signing_keys(id_token)
            claims = jwt.decode(id_token, keys, algorithms=ID_TOKEN_ALGORITHMS).claims
            self._claims_registry(nonce).validate(claims)
        except InvalidClaimError as error:
            nonce_differs = error.claim == "nonce"
            raise LoginError(
                LoginFailureReason.NONCE_MISMATCH
                if nonce_differs
                else LoginFailureReason.INVALID_ID_TOKEN
            ) from error
        except httpx.HTTPError as error:
            raise LoginError(LoginFailureReason.KEYS_UNAVAILABLE) from error
        except (JoseError, ValueError) as error:
            raise LoginError(LoginFailureReason.INVALID_ID_TOKEN) from error
        return LoginIdentity(customer_id=claims["preferred_username"], subject=claims["sub"])

    def _claims_registry(self, nonce: str) -> jwt.JWTClaimsRegistry:
        """Builds the claim rules an ID token of this login must satisfy.

        Args:
            nonce: The nonce this login sent.

        Returns:
            jwt.JWTClaimsRegistry: rules for iss, aud, exp, nonce and the customer's username.
        """
        return jwt.JWTClaimsRegistry(
            now=int(self._clock().timestamp()),
            iss={"essential": True, "value": self._config.issuer},
            aud={"essential": True, "value": self._config.client_id},
            exp={"essential": True},
            nonce={"essential": True, "value": nonce},
            sub={"essential": True},
            preferred_username={"essential": True},
        )

    def _signing_keys(self, id_token: str) -> KeySet:
        """Returns the realm's public keys, fetching them again if the token's key is new.

        Args:
            id_token: The token whose `kid` must be among the keys.

        Returns:
            KeySet: Keycloak's current signing keys.
        """
        key_id = jws.extract_compact(id_token.encode("ascii")).headers().get("kid")
        if self._key_set is None or not any(key.kid == key_id for key in self._key_set.keys):
            response = self._http.get(self._config.endpoint(KeycloakEndpoint.CERTS))
            response.raise_for_status()
            self._key_set = KeySet.import_key_set(response.json())
        return self._key_set
