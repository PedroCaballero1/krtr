"""Defines the session routes: GET /api/me and POST /api/session/activity (task 4.4).

Exists so the frontend learns who is logged in and both session deadlines (to warn 30 s before
each, D13), and reports activity at most every 60 s, which pushes the idle deadline back.
Expired sessions answer 401 through the session error handler. Consumed by
`krtr/back/web/app.py`.
"""

from fastapi import APIRouter, Depends

from krtr.back.security.sessions.artifacts import SessionRecord, SessionStatus
from krtr.back.web.csrf import require_session_with_csrf
from krtr.back.web.dependencies import AuthServices, get_auth_services, require_session

session_router = APIRouter(prefix="/api")


@session_router.get("/me")
def get_current_session(
    session: SessionRecord = Depends(require_session),
    services: AuthServices = Depends(get_auth_services),
) -> SessionStatus:
    """Returns the logged-in customer and the session's deadlines, without counting as activity.

    Args:
        session: The request's live session.
        services: The app's login and session services.

    Returns:
        SessionStatus: `{customer_id, idle_expires_at, absolute_expires_at}` (§3.4).
    """
    return services.session_service.status(session)


@session_router.post("/session/activity")
def record_session_activity(
    session: SessionRecord = Depends(require_session_with_csrf),
    services: AuthServices = Depends(get_auth_services),
) -> SessionStatus:
    """Records the customer's activity and returns the session's new deadlines.

    Args:
        session: The request's live session.
        services: The app's login and session services.

    Returns:
        SessionStatus: the same shape as GET /api/me, with the idle deadline pushed back.
    """
    return services.session_service.record_activity(session)
