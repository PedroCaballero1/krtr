"""Defines the OIDC login routes: /auth/login, /auth/callback and /auth/logout (task 4.3).

Exists as the backend-for-frontend's half of the login (§3.2 of
docs/guia-web-seguridad_modal.md): the browser only ever holds the session cookie, never a
token. Every step is recorded (`auth_login_started`, `auth_login_succeeded`,
`auth_login_failed`, `auth_logout`, `session_created`, `session_revoked_by_new_login`).
Consumed by `krtr/back/web/app.py`.
"""

import logging
import secrets

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from fastapi.responses import RedirectResponse

from krtr.back.security.audit.event_names import EventName
from krtr.back.security.oidc.artifacts import (
    InterfaceLanguage,
    LoginIdentity,
    LoginState,
    OidcTokens,
)
from krtr.back.security.oidc.config import LOGIN_COOKIE_NAME
from krtr.back.security.oidc.errors import LoginError, LoginFailureReason
from krtr.back.security.sessions.artifacts import SessionRecord
from krtr.back.web.auditing import schedule_event
from krtr.back.web.cookies import (
    clear_login_cookie,
    clear_session_cookie,
    set_login_cookie,
    set_session_cookie,
)
from krtr.back.web.dependencies import AuthServices, get_auth_services, require_session
from krtr.back.web.errors import ApiErrorCode, MessageKey, api_error

logger = logging.getLogger(__name__)

APP_HOME_PATH = "/app"  # The SPA's authenticated home (AppPath.Home in the frontend).

auth_router = APIRouter(prefix="/auth")


@auth_router.get("/login", include_in_schema=False)
def login(
    request: Request,
    tasks: BackgroundTasks,
    lang: InterfaceLanguage = InterfaceLanguage.SPANISH,
    services: AuthServices = Depends(get_auth_services),
) -> RedirectResponse:
    """Starts a login: stores its secrets in the login cookie and redirects to Keycloak.

    Args:
        request: The current request.
        tasks: Where the event is queued.
        lang: The interface language, which Keycloak shows the login in (D14).
        services: The app's login and session services.

    Returns:
        RedirectResponse: 302 to Keycloak's login page.
    """
    login_state, url = services.oidc_client.start_login(lang)
    response = RedirectResponse(url, status_code=302)
    set_login_cookie(response, services.login_codec.encode(login_state))
    schedule_event(request, tasks, EventName.AUTH_LOGIN_STARTED, {"language": lang.value})
    return response


@auth_router.get("/callback", include_in_schema=False)
def callback(
    request: Request,
    tasks: BackgroundTasks,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    services: AuthServices = Depends(get_auth_services),
) -> Response:
    """Finishes a login: checks it, opens the session, and sends the customer to /app.

    Args:
        request: The callback, carrying the login cookie.
        tasks: Where the events are queued.
        code: The authorization code from Keycloak.
        state: The state Keycloak echoes back.
        error: Keycloak's error, when the login did not complete.
        services: The app's login and session services.

    Returns:
        Response: 302 to /app with the session cookie, or 400 if the login is rejected.
    """
    try:
        login_state = services.login_codec.decode(
            request.cookies.get(LOGIN_COOKIE_NAME), services.clock()
        )
        authorization_code = _checked_code(login_state, state, code, error)
        identity, tokens = services.oidc_client.complete_login(login_state, authorization_code)
    except LoginError as failure:
        return _reject_login(request, tasks, failure)
    return _open_session(request, tasks, services, identity, tokens)


@auth_router.post("/logout", status_code=204, include_in_schema=False)
def logout(
    request: Request,
    tasks: BackgroundTasks,
    session: SessionRecord = Depends(require_session),
    services: AuthServices = Depends(get_auth_services),
) -> Response:
    """Logs out of krtr and of Keycloak, and clears the session cookie.

    Args:
        request: The current request.
        tasks: Where the event is queued.
        session: The live session being closed.
        services: The app's login and session services.

    Returns:
        Response: 204.
    """
    services.oidc_client.end_session(session.tokens)
    services.session_service.end(session)
    response = Response(status_code=204)
    clear_session_cookie(response)
    schedule_event(request, tasks, EventName.AUTH_LOGOUT, {"customer_id": session.customer_id})
    return response


def _checked_code(
    login_state: LoginState, state: str | None, code: str | None, error: str | None
) -> str:
    """Checks that the callback answers this browser's login, and returns its code.

    The state is checked first, in constant time, so nothing else of a callback that is not
    ours is trusted.

    Args:
        login_state: The login this browser started.
        state: The state in the callback.
        code: The authorization code in the callback.
        error: Keycloak's error in the callback, if any.

    Returns:
        str: the authorization code.

    Raises:
        LoginError: STATE_MISMATCH, PROVIDER_ERROR or MISSING_CODE.
    """
    if state is None or not secrets.compare_digest(state, login_state.state):
        raise LoginError(LoginFailureReason.STATE_MISMATCH)
    if error is not None:
        raise LoginError(LoginFailureReason.PROVIDER_ERROR)
    if not code:
        raise LoginError(LoginFailureReason.MISSING_CODE)
    return code


def _reject_login(request: Request, tasks: BackgroundTasks, failure: LoginError) -> Response:
    """Answers a rejected callback with 400, clearing the login cookie and recording why.

    Args:
        request: The callback.
        tasks: Where the event is queued.
        failure: Why the login was rejected.

    Returns:
        Response: 400 with the §3.4 body.
    """
    logger.warning("Rejected a login callback: %s", failure.reason.value)
    response = api_error(400, ApiErrorCode.LOGIN_FAILED, MessageKey.LOGIN_FAILED)
    clear_login_cookie(response)
    schedule_event(request, tasks, EventName.AUTH_LOGIN_FAILED, {"reason": failure.reason.value})
    return response


def _open_session(
    request: Request,
    tasks: BackgroundTasks,
    services: AuthServices,
    identity: LoginIdentity,
    tokens: OidcTokens,
) -> Response:
    """Opens the customer's session (closing earlier ones) and redirects to /app.

    Args:
        request: The callback.
        tasks: Where the events are queued.
        services: The app's login and session services.
        identity: Who logged in.
        tokens: The tokens Keycloak issued.

    Returns:
        Response: 302 to /app with the session cookie set and the login cookie cleared.
    """
    started = services.session_service.start(identity.customer_id, tokens)
    response = RedirectResponse(APP_HOME_PATH, status_code=302)
    set_session_cookie(response, started.token)
    clear_login_cookie(response)
    customer = {"customer_id": identity.customer_id}
    schedule_event(request, tasks, EventName.AUTH_LOGIN_SUCCEEDED, customer)
    schedule_event(request, tasks, EventName.SESSION_CREATED, customer)
    if started.replaced_sessions:
        replaced = {**customer, "replaced_sessions": started.replaced_sessions}
        schedule_event(request, tasks, EventName.SESSION_REVOKED_BY_NEW_LOGIN, replaced)
    return response
