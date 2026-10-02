"""Defines the error raised when a request carries no usable session (task 4.4).

Exists so the reason (and, when known, the customer) travels to the router, which answers 401
and records `unauthorized_request` plus the matching `session_expired_*` event. Raised by
`krtr/back/security/sessions/service.py`.
"""

from krtr.back.security.sessions.artifacts import SessionEndReason


class SessionRejected(Exception):
    """Raised when a session cookie does not open a live session.

    Exists so callers handle every way a session can be unusable with one exception.
    Consumed by `krtr/back/web/routers/`.
    """

    def __init__(self, reason: SessionEndReason, customer_id: str | None = None) -> None:
        """Builds the error for one reason.

        Args:
            reason: Why the session is unusable.
            customer_id: The session's customer, when the session existed.
        """
        super().__init__(reason.value)
        self.reason = reason
        self.customer_id = customer_id
