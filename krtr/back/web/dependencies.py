"""Wires krtr-web's login and session services into its routes (tasks 4.3 and 4.4).

Exists so routes get the OIDC client and the session service through FastAPI dependencies,
and so every rejected session ends the same way: 401 with the §3.4 body, the session cookie
cleared, and `unauthorized_request` (plus `session_expired_idle` / `session_expired_absolute`)
recorded (G21, P5.4). Consumed by `krtr/back/web/app.py` and `krtr/back/web/routers/`.
"""

import logging
from dataclasses import dataclass
from typing import Protocol

from fastapi import BackgroundTasks, Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from krtr.back.security.audit.event_names import EventName
from krtr.back.security.clock import Clock, utc_now
from krtr.back.security.oidc.artifacts import (
    InterfaceLanguage,
    LoginIdentity,
    LoginState,
    OidcTokens,
)
from krtr.back.security.oidc.login_cookie import LoginCookieCodec
from krtr.back.security.sessions.artifacts import SessionEndReason, SessionRecord
from krtr.back.security.sessions.config import SESSION_COOKIE_NAME
from krtr.back.security.sessions.errors import SessionRejected
from krtr.back.security.sessions.service import SessionService
from krtr.back.web.auditing import schedule_event
from krtr.back.web.cookies import clear_csrf_cookie, clear_session_cookie
from krtr.back.web.errors import ApiErrorCode, MessageKey, api_error

logger = logging.getLogger(__name__)

# How each expiry is reported: error code, i18n key, and the event that records it.
_EXPIRY_RESPONSES = {
    SessionEndReason.IDLE: (
        ApiErrorCode.SESSION_EXPIRED_IDLE,
        MessageKey.SESSION_EXPIRED_IDLE,
        EventName.SESSION_EXPIRED_IDLE,
    ),
    SessionEndReason.ABSOLUTE: (
        ApiErrorCode.SESSION_EXPIRED_ABSOLUTE,
        MessageKey.SESSION_EXPIRED_ABSOLUTE,
        EventName.SESSION_EXPIRED_ABSOLUTE,
    ),
}


class OidcLoginClient(Protocol):
    """What the routes need from the OIDC client (KeycloakOidcClient; a fake in tests)."""

    def start_login(self, language: InterfaceLanguage) -> tuple[LoginState, str]:
        """Returns a new login's state and Keycloak's login URL."""

    def complete_login(
        self, login_state: LoginState, code: str
    ) -> tuple[LoginIdentity, OidcTokens]:
        """Exchanges the code and validates the ID token, raising LoginError if not valid."""

    def end_session(self, tokens: OidcTokens) -> None:
        """Ends the Keycloak session and revokes the refresh token, best effort."""


@dataclass(frozen=True)
class AuthServices:
    """The login and session collaborators krtr-web serves with.

    Exists so the app holds them as one unit: production builds them from the environment
    (`create_served_app`), tests inject fakes. Consumed through `get_auth_services`.
    """

    oidc_client: OidcLoginClient
    login_codec: LoginCookieCodec
    session_service: SessionService
    clock: Clock = utc_now


class AuthUnavailable(Exception):
    """Raised when a login or session route is called but login is not configured.

    Exists for development without Keycloak: the rest of the app keeps working, and these
    routes answer 503 instead of crashing. Production never starts without login.
    """


def get_auth_services(request: Request) -> AuthServices:
    """Returns the app's login and session services.

    Args:
        request: The current request, to reach the app's state.

    Returns:
        AuthServices: the configured services.

    Raises:
        AuthUnavailable: if the app was built without them.
    """
    services: AuthServices | None = getattr(request.app.state, "auth_services", None)
    if services is None:
        raise AuthUnavailable()
    return services


def require_session(
    request: Request, services: AuthServices = Depends(get_auth_services)
) -> SessionRecord:
    """Returns the request's live session, for routes that need a logged-in customer.

    Args:
        request: The current request, carrying the session cookie.
        services: The app's login and session services.

    Returns:
        SessionRecord: the live session.

    Raises:
        SessionRejected: if the cookie opens no live session (answered 401 by the handler).
    """
    return services.session_service.authenticate(request.cookies.get(SESSION_COOKIE_NAME))


async def handle_session_rejected(request: Request, error: SessionRejected) -> JSONResponse:
    """Answers a rejected session with 401, clears its cookies, and records why.

    Args:
        request: The rejected request.
        error: Why the session was rejected, and its customer when known.

    Returns:
        JSONResponse: 401 with the §3.4 body.
    """
    code, message_key, expiry_event = _EXPIRY_RESPONSES.get(
        error.reason, (ApiErrorCode.UNAUTHORIZED, MessageKey.UNAUTHORIZED, None)
    )
    response = api_error(401, code, message_key)
    clear_session_cookie(response)
    clear_csrf_cookie(response)
    tasks = BackgroundTasks()
    reason = {"path": request.url.path, "reason": error.reason.value}
    schedule_event(request, tasks, EventName.UNAUTHORIZED_REQUEST, reason)
    if expiry_event is not None:
        schedule_event(request, tasks, expiry_event, {"customer_id": error.customer_id})
    response.background = tasks
    return response


async def handle_auth_unavailable(request: Request, error: AuthUnavailable) -> JSONResponse:
    """Answers login and session routes with 503 while login is not configured.

    Args:
        request: The request.
        error: The (empty) error.

    Returns:
        JSONResponse: 503 with the §3.4 body.
    """
    logger.warning("Login is not configured; %s answered 503", request.url.path)
    return api_error(503, ApiErrorCode.AUTH_UNAVAILABLE, MessageKey.AUTH_UNAVAILABLE)


def register_auth_error_handlers(app: FastAPI) -> None:
    """Registers the handlers that turn session and configuration errors into responses.

    Args:
        app: The app to register them on.

    Returns:
        None.
    """
    app.add_exception_handler(SessionRejected, handle_session_rejected)
    app.add_exception_handler(AuthUnavailable, handle_auth_unavailable)
