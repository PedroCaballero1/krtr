"""Encodes the encrypted, short-lived login cookie `__Host-krtr_oidc` (task 4.3, D22).

Exists so the login's state, nonce and PKCE verifier survive the round trip to Keycloak without
server-side storage, while the browser can neither read nor forge them: the cookie is
AES-256-GCM encrypted with the tokens key and expires after 10 minutes. Consumed by
`krtr/back/web/routers/auth.py`.
"""

import base64
import binascii
from datetime import datetime

from cryptography.exceptions import InvalidTag
from pydantic import ValidationError

from krtr.back.security.crypto.cipher import AesGcmCipher
from krtr.back.security.oidc.artifacts import LoginState
from krtr.back.security.oidc.errors import LoginError, LoginFailureReason


class LoginCookieCodec:
    """Turns a LoginState into an opaque cookie value and back.

    Exists so the cookie's format (encrypted JSON, base64url) and its checks live in one class.
    Consumed by the auth router: `encode` at /auth/login, `decode` at /auth/callback.
    """

    def __init__(self, cipher: AesGcmCipher) -> None:
        """Builds a codec bound to the tokens key.

        Args:
            cipher: The AES-256-GCM cipher for the tokens key (KRTR_TOKENS_KEY).
        """
        self._cipher = cipher

    def encode(self, login_state: LoginState) -> str:
        """Encrypts a login state into a cookie value.

        Args:
            login_state: The state, nonce, PKCE verifier and language of the login.

        Returns:
            str: the base64url-encoded ciphertext, safe as a cookie value.
        """
        ciphertext = self._cipher.encrypt(login_state.model_dump_json().encode("utf-8"))
        return base64.urlsafe_b64encode(ciphertext).decode("ascii")

    def decode(self, value: str | None, now: datetime) -> LoginState:
        """Decrypts a cookie value and checks it has not expired.

        Args:
            value: The cookie value, or None when the browser sent no login cookie.
            now: The current time, compared with the login's expiry.

        Returns:
            LoginState: the login this browser started.

        Raises:
            LoginError: if the cookie is missing, cannot be decrypted, or has expired.
        """
        if not value:
            raise LoginError(LoginFailureReason.MISSING_LOGIN_COOKIE)
        login_state = self._decrypt(value)
        if now >= login_state.expires_at:
            raise LoginError(LoginFailureReason.EXPIRED_LOGIN)
        return login_state

    def _decrypt(self, value: str) -> LoginState:
        """Decrypts and parses a cookie value, treating any failure as a forged cookie.

        Args:
            value: The cookie value.

        Returns:
            LoginState: the decrypted login state.

        Raises:
            LoginError: if the value is not valid base64, fails authentication, or does not
                hold a login state.
        """
        try:
            plaintext = self._cipher.decrypt(base64.urlsafe_b64decode(value.encode("ascii")))
            return LoginState.model_validate_json(plaintext)
        except (binascii.Error, InvalidTag, ValueError, ValidationError, UnicodeError) as error:
            raise LoginError(LoginFailureReason.INVALID_LOGIN_COOKIE) from error
