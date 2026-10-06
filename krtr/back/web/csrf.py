"""Wires the CSRF protection into krtr-web's state-changing routes (task 4.5).

Exists so a route opts in with one dependency, and every rejection ends the same way: 403 with
the §3.4 body and a `csrf_rejected` event. Three levels:

- `require_same_origin`: the Origin check alone, for `POST /api/events`, which the landing page
  calls before any session (and so any CSRF cookie) exists.
- `require_csrf`: the Origin check plus the double submit.
- `require_session_with_csrf`: the session first, then `require_csrf`, for every state-changing
  route that needs a logged-in customer. A request without a session answers 401 (so the SPA
  goes back to the landing page), not 403.

Consumed by `krtr/back/web/app.py` and `krtr/back/web/routers/`.
"""

import logging

from fastapi import BackgroundTasks, Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from krtr.back.security.audit.event_names import EventName
from krtr.back.security.csrf.config import CSRF_COOKIE_NAME, CSRF_HEADER_NAME, CsrfConfig
from krtr.back.security.csrf.errors import CsrfRejected
from krtr.back.security.csrf.guard import check_origin, check_token
from krtr.back.security.sessions.artifacts import SessionRecord
from krtr.back.web.auditing import schedule_event
from krtr.back.web.dependencies import require_session
from krtr.back.web.errors import ApiErrorCode, MessageKey, api_error

logger = logging.getLogger(__name__)


def require_same_origin(request: Request) -> None:
    """Rejects a request whose Origin (or Referer) is not krtr-web's own.

    Args:
        request: The current request.

    Returns:
        None.

    Raises:
        CsrfRejected: if the request names another origin, or none.
    """
    config: CsrfConfig = request.app.state.csrf_config
    check_origin(
        request.headers.get("origin"), request.headers.get("referer"), config.allowed_origin
    )


def require_csrf(request: Request) -> None:
    """Rejects a request that fails the Origin check or the double submit.

    Args:
        request: The current request.

    Returns:
        None.

    Raises:
        CsrfRejected: if either check fails.
    """
    require_same_origin(request)
    check_token(request.cookies.get(CSRF_COOKIE_NAME), request.headers.get(CSRF_HEADER_NAME))


def require_session_with_csrf(
    request: Request, session: SessionRecord = Depends(require_session)
) -> SessionRecord:
    """Returns the request's live session, once the request also passes the CSRF checks.

    Args:
        request: The current request.
        session: The request's live session (resolved first, so no session means 401).

    Returns:
        SessionRecord: the live session.

    Raises:
        CsrfRejected: if the request fails the Origin check or the double submit.
    """
    require_csrf(request)
    return session


async def handle_csrf_rejected(request: Request, error: CsrfRejected) -> JSONResponse:
    """Answers a rejected request with 403 and records why.

    Args:
        request: The rejected request.
        error: Why it was rejected.

    Returns:
        JSONResponse: 403 with the §3.4 body.
    """
    logger.warning("Rejected %s %s: %s", request.method, request.url.path, error.reason.value)
    response = api_error(403, ApiErrorCode.CSRF_REJECTED, MessageKey.CSRF_REJECTED)
    tasks = BackgroundTasks()
    properties = {"path": request.url.path, "reason": error.reason.value}
    schedule_event(request, tasks, EventName.CSRF_REJECTED, properties)
    response.background = tasks
    return response


def register_csrf_error_handler(app: FastAPI) -> None:
    """Registers the handler that turns a CSRF rejection into a 403.

    Args:
        app: The app to register it on.

    Returns:
        None.
    """
    app.add_exception_handler(CsrfRejected, handle_csrf_rejected)
