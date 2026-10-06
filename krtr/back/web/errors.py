"""Defines krtr-web's API error responses.

Exists so every error the API returns has the `{error, message_key}` shape of §3.4 of
docs/guia-web-seguridad_modal.md: `error` is a stable code, `message_key` an i18n key the
frontend translates. Consumed by `krtr/back/web/dependencies.py` and `krtr/back/web/routers/`.
"""

from enum import StrEnum

from fastapi.responses import JSONResponse


class ApiErrorCode(StrEnum):
    """The `error` codes the API answers with.

    Exists so codes are never typed as raw strings. Consumed by the routers and handlers.
    """

    UNAUTHORIZED = "unauthorized"  # No session, or one that was revoked or forged.
    SESSION_EXPIRED_IDLE = "session_expired_idle"
    SESSION_EXPIRED_ABSOLUTE = "session_expired_absolute"
    LOGIN_FAILED = "login_failed"  # The OIDC callback was rejected (task 4.3).
    AUTH_UNAVAILABLE = "auth_unavailable"  # Login is not configured (development only).
    CSRF_REJECTED = "csrf_rejected"  # Foreign origin, or no matching X-KRTR-CSRF (task 4.5).
    CASE_NOT_FOUND = "case_not_found"  # Also another customer's case: the same 404 (task 4.8).
    AUDIO_TOO_LARGE = "audio_too_large"  # A voice note over 2 MB (task 4.9).
    UNSUPPORTED_AUDIO = "unsupported_audio"  # Not WebM/MP4 audio, by type or by its bytes.
    REQUEST_TOO_LARGE = "request_too_large"  # Any body over the app-wide limit.


class MessageKey(StrEnum):
    """The i18n keys sent as `message_key`; those the frontend has match its locale files.

    Exists so the backend and `krtr/front/src/i18n/locales/` agree on the keys.
    """

    UNAUTHORIZED = "unauthorized"
    SESSION_EXPIRED_IDLE = "session_expired_idle_message"
    SESSION_EXPIRED_ABSOLUTE = "session_expired_absolute_message"
    LOGIN_FAILED = "login_failed"
    AUTH_UNAVAILABLE = "auth_unavailable"
    CSRF_REJECTED = "csrf_rejected"
    CASE_NOT_FOUND = "support_case_not_found"
    AUDIO_TOO_LARGE = "chat_error_voice_too_large"
    UNSUPPORTED_AUDIO = "chat_error_voice_unsupported"
    REQUEST_TOO_LARGE = "request_too_large"


def api_error(status_code: int, code: ApiErrorCode, message_key: MessageKey) -> JSONResponse:
    """Builds an error response with the §3.4 body.

    Args:
        status_code: The HTTP status.
        code: The stable error code.
        message_key: The i18n key the frontend translates.

    Returns:
        JSONResponse: `{"error": code, "message_key": message_key}` with that status.
    """
    return JSONResponse(
        status_code=status_code, content={"error": code.value, "message_key": message_key.value}
    )
