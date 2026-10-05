"""Fakes shared by the web tests: a stand-in Keycloak client and an app wired with fakes."""

from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import urlencode

from fastapi.testclient import TestClient

from krtr.back.security.audit.event_names import EventName
from krtr.back.security.crypto.cipher import AesGcmCipher
from krtr.back.security.oidc.artifacts import (
    InterfaceLanguage,
    LoginIdentity,
    LoginState,
    OidcTokens,
)
from krtr.back.security.oidc.config import LOGIN_COOKIE_LIFETIME
from krtr.back.security.oidc.errors import LoginError, LoginFailureReason
from krtr.back.security.oidc.login_cookie import LoginCookieCodec
from krtr.back.security.sessions.service import SessionService
from krtr.back.web.app import create_app
from krtr.back.web.config import WebConfig
from krtr.back.web.dependencies import AuthServices
from tests.back.security.audit.fakes import InMemoryRecorder
from tests.back.security.oidc.fakes import FakeClock
from tests.back.security.sessions.fakes import (
    FakeRefresher,
    InMemorySessionStore,
    tokens_expiring_at,
)

CUSTOMER = "12345678"
AUTHORIZE_URL = "http://keycloak.test/realms/krtr/protocol/openid-connect/auth"


class FakeOidcClient:
    """Stands in for KeycloakOidcClient: issues numbered logins and accepts or rejects codes."""

    def __init__(self, clock: FakeClock) -> None:
        """Accepts every code for CUSTOMER until told to reject."""
        self.clock = clock
        self.started: list[LoginState] = []
        self.exchanged_codes: list[str] = []
        self.ended_sessions: list[OidcTokens] = []
        self.rejection: LoginFailureReason | None = None
        self.customer_id = CUSTOMER

    def start_login(self, language: InterfaceLanguage) -> tuple[LoginState, str]:
        """Returns a new login with predictable secrets and a Keycloak-like URL."""
        number = len(self.started) + 1
        login_state = LoginState(
            state=f"state-{number}",
            nonce=f"nonce-{number}",
            code_verifier=f"verifier-{number}",
            language=language,
            expires_at=self.clock() + LOGIN_COOKIE_LIFETIME,
        )
        self.started.append(login_state)
        query = urlencode({"state": login_state.state, "ui_locales": language.value})
        return login_state, f"{AUTHORIZE_URL}?{query}"

    def complete_login(
        self, login_state: LoginState, code: str
    ) -> tuple[LoginIdentity, OidcTokens]:
        """Returns the customer's identity and 5-minute tokens, or raises the set rejection."""
        self.exchanged_codes.append(code)
        if self.rejection is not None:
            raise LoginError(self.rejection)
        identity = LoginIdentity(customer_id=self.customer_id, subject=f"sub-{self.customer_id}")
        tokens = tokens_expiring_at(
            self.clock() + timedelta(minutes=5), generation=len(self.exchanged_codes)
        )
        return identity, tokens

    def end_session(self, tokens: OidcTokens) -> None:
        """Remembers which tokens were logged out of Keycloak."""
        self.ended_sessions.append(tokens)


@dataclass
class WebHarness:
    """An app wired with fakes, and the fakes themselves, for the router tests."""

    client: TestClient
    clock: FakeClock
    oidc: FakeOidcClient
    store: InMemorySessionStore
    refresher: FakeRefresher
    recorder: InMemoryRecorder

    def recorded(self) -> list[str]:
        """Returns the names of the events the routes recorded, in order (not http_request)."""
        return [name.value for name, _ in self.recorder.events if name != EventName.HTTP_REQUEST]

    def properties_of(self, event_name: EventName) -> dict:
        """Returns the properties of the last recorded event with that name."""
        return [properties for name, properties in self.recorder.events if name == event_name][-1]

    def log_in(self, customer_id: str = CUSTOMER) -> str:
        """Runs /auth/login and a successful /auth/callback; returns the session cookie value."""
        self.oidc.customer_id = customer_id
        self.client.get("/auth/login", follow_redirects=False)
        state = self.oidc.started[-1].state
        response = self.client.get(
            f"/auth/callback?code=code-1&state={state}", follow_redirects=False
        )
        assert response.status_code == 302, response.text
        return response.cookies["__Host-krtr_session"]


def build_harness(config: WebConfig | None = None) -> WebHarness:
    """Builds the app with fake Keycloak, in-memory sessions and events, and a fake clock.

    The client talks https, so the `__Host-` (Secure) cookies are sent back like a browser does.
    """
    clock = FakeClock()
    oidc = FakeOidcClient(clock)
    store = InMemorySessionStore()
    refresher = FakeRefresher(clock)
    recorder = InMemoryRecorder()
    services = AuthServices(
        oidc_client=oidc,
        login_codec=LoginCookieCodec(AesGcmCipher(b"k" * 32)),
        session_service=SessionService(store, refresher, clock=clock),
        clock=clock,
    )
    app = create_app(config or WebConfig(), event_recorder=recorder, auth_services=services)
    client = TestClient(app, base_url="https://testserver")
    return WebHarness(client, clock, oidc, store, refresher, recorder)
