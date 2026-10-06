"""Defines why an OIDC login can fail (task 4.3).

Exists so every failure of the login callback carries one reason from a closed set, which the
router turns into a redirect to the landing page and an `auth_login_failed` event. Consumed by
`krtr/back/security/oidc/` and `krtr/back/web/routers/auth.py`.
"""

from enum import StrEnum


class LoginFailureReason(StrEnum):
    """The reasons a login callback is rejected, as recorded in `auth_login_failed` events."""

    MISSING_LOGIN_COOKIE = "missing_login_cookie"  # No /auth/login in this browser, or expired.
    INVALID_LOGIN_COOKIE = "invalid_login_cookie"  # Tampered with, or encrypted with another key.
    EXPIRED_LOGIN = "expired_login"  # More than 10 minutes between /auth/login and the callback.
    STATE_MISMATCH = "state_mismatch"  # The callback does not answer this browser's login.
    PROVIDER_ERROR = "provider_error"  # Keycloak redirected back with `?error=`.
    MISSING_CODE = "missing_code"
    TOKEN_EXCHANGE_FAILED = "token_exchange_failed"
    INVALID_ID_TOKEN = "invalid_id_token"  # Bad signature, issuer, audience or expiry.
    KEYS_UNAVAILABLE = "keys_unavailable"  # Keycloak's signing keys could not be fetched.
    NONCE_MISMATCH = "nonce_mismatch"  # The ID token was not issued for this login.


class LoginError(Exception):
    """Raised when a login callback must be rejected.

    Exists so the reason travels with the exception up to the router, which sends the browser
    back to the landing page and records it. Raised by `krtr/back/security/oidc/`.
    """

    def __init__(self, reason: LoginFailureReason) -> None:
        """Builds the error for one failure reason.

        Args:
            reason: Why the login was rejected.
        """
        super().__init__(reason.value)
        self.reason = reason
