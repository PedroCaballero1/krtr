"""Defines why a request fails the CSRF check (task 4.5).

Exists so every rejection carries one reason from a closed set, which the web layer turns into
a 403 and a `csrf_rejected` event. Raised by `krtr/back/security/csrf/guard.py`.
"""

from enum import StrEnum


class CsrfFailureReason(StrEnum):
    """The reasons a state-changing request is rejected, as recorded in `csrf_rejected`."""

    MISSING_ORIGIN = "missing_origin"  # Neither Origin nor Referer names an origin.
    FOREIGN_ORIGIN = "foreign_origin"  # Another site, including another *.modal.run app.
    MISSING_TOKEN = "missing_token"  # The CSRF cookie or the X-KRTR-CSRF header is absent.
    TOKEN_MISMATCH = "token_mismatch"  # The header does not echo the cookie.


class CsrfRejected(Exception):
    """Raised when a request must be rejected by the CSRF protection.

    Exists so the reason travels to the handler that answers 403 and records it.
    Consumed by `krtr/back/web/csrf.py`.
    """

    def __init__(self, reason: CsrfFailureReason) -> None:
        """Builds the error for one failure reason.

        Args:
            reason: Why the request was rejected.
        """
        super().__init__(reason.value)
        self.reason = reason
