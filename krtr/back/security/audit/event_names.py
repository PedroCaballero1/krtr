"""Defines the catalog of event names the `events` table accepts.

Exists so no part of the system hardcodes an event name string: every event
recorded by the backend, or submitted by the frontend to `POST /api/events`,
must be a member of this Enum. Mirrors the catalog documented in §3.5 of
docs/guia-web-seguridad_modal.md. Consumed by `krtr/back/security/audit/recorder.py`
and `krtr/back/web/routers/events.py`.

Not covered here: the `auth_*` events Keycloak itself emits (login,
logout, ...), synced from `keycloak.event_entity` by the
`sync-auth-events` job (task 4.10, D3). That set is defined by Keycloak,
not by this codebase, so it is written directly rather than validated
against this Enum.
"""

from enum import StrEnum


class EventName(StrEnum):
    """The fixed set of event names this backend can record or accept.

    Used to validate `POST /api/events` and every `record_event` call, so a
    typo or an unplanned event name fails fast instead of silently writing
    an unrecognized string to the audit log.
    """

    # HTTP — recorded by the audit middleware for every request.
    HTTP_REQUEST = "http_request"  # method, route, status, latency, IP, user-agent, request_id.

    # Login / session.
    AUTH_LOGIN_STARTED = "auth_login_started"
    AUTH_LOGIN_SUCCEEDED = "auth_login_succeeded"
    AUTH_LOGIN_FAILED = "auth_login_failed"
    AUTH_LOGOUT = "auth_logout"
    SESSION_CREATED = "session_created"
    SESSION_REVOKED_BY_NEW_LOGIN = "session_revoked_by_new_login"
    SESSION_IDLE_WARNING_SHOWN = "session_idle_warning_shown"
    SESSION_ABSOLUTE_WARNING_SHOWN = "session_absolute_warning_shown"
    SESSION_EXTENDED = "session_extended"
    SESSION_EXPIRED_IDLE = "session_expired_idle"
    SESSION_EXPIRED_ABSOLUTE = "session_expired_absolute"

    # Interface.
    PAGE_VIEW = "page_view"
    LANGUAGE_CHANGED = "language_changed"
    SUPPORT_CLICKED = "support_clicked"
    CASE_MODE_SELECTED = "case_mode_selected"
    CASE_LIST_VIEWED = "case_list_viewed"
    CASE_CREATED = "case_created"
    CASE_RESUME_SUCCEEDED = "case_resume_succeeded"
    CASE_RESUME_FAILED = "case_resume_failed"

    # Chat.
    CHAT_MESSAGE_SENT = "chat_message_sent"
    CHAT_RESPONSE_RECEIVED = "chat_response_received"  # Includes response latency.
    TYPING_INDICATOR_SHOWN = "typing_indicator_shown"

    # Voice.
    VOICE_RECORDING_STARTED = "voice_recording_started"
    VOICE_RECORDING_CANCELLED = "voice_recording_cancelled"
    VOICE_RECORDING_SENT = "voice_recording_sent"
    VOICE_PERMISSION_DENIED = "voice_permission_denied"

    # Security.
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    CSRF_REJECTED = "csrf_rejected"
    UNAUTHORIZED_REQUEST = "unauthorized_request"
    CLIENT_ERROR = "client_error"
    SERVER_ERROR = "server_error"
