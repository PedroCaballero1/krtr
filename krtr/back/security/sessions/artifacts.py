"""Defines the contracts of krtr-web's server-side sessions (task 4.4).

Exists to keep what a session is, what the API reports about it, and why one can end,
discoverable apart from the code that enforces the rules. Consumed by
`krtr/back/security/sessions/` and `krtr/back/web/routers/`.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel

from krtr.back.security.oidc.artifacts import OidcTokens


class SessionEndReason(StrEnum):
    """Why a request's session cookie no longer opens a session.

    Exists so the API's 401 and the recorded event say why, e.g. `session_expired_idle`.
    Consumed by the session service and the routers.
    """

    UNKNOWN = "unknown"  # No session with that token: never existed, forged, or no cookie.
    REVOKED = "revoked"  # Logged out, replaced by a newer login, or its tokens were refused.
    IDLE = "idle"  # 5 minutes without activity (G15).
    ABSOLUTE = "absolute"  # 30 minutes since login (G15).


class SessionRecord(BaseModel):
    """One row of `app_sessions`, with its OIDC tokens decrypted.

    Exists so the service works with typed sessions instead of database rows.
    """

    session_id_hash: str
    customer_id: str
    tokens: OidcTokens
    created_at: datetime
    last_activity_at: datetime
    absolute_expires_at: datetime
    revoked_at: datetime | None = None


class SessionStatus(BaseModel):
    """What `GET /api/me` and `POST /api/session/activity` return (§3.4).

    Exists so the frontend can warn 30 seconds before either deadline (D13).
    """

    customer_id: str
    idle_expires_at: datetime
    absolute_expires_at: datetime


class StartedSession(BaseModel):
    """The result of a login: the cookie value, the session's status, and whom it replaced.

    Exists so the router can set the cookie and record `session_revoked_by_new_login` only when
    an earlier session was really closed.
    """

    token: str  # The session cookie's value; never stored, never logged.
    status: SessionStatus
    replaced_sessions: int
