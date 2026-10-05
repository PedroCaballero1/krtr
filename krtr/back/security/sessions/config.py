"""Defines the settings of krtr-web's server-side sessions (task 4.4, G15).

Exists so the session rules — 5 minutes idle, 30 minutes at most, refreshing the access token
shortly before it expires — and the session cookie are declared in one place. Consumed by
`krtr/back/security/sessions/service.py` and `krtr/back/web/routers/`.
"""

from datetime import timedelta

from pydantic import BaseModel

# HttpOnly, Secure, SameSite=Strict; `__Host-` so no other *.modal.run app can overwrite it.
SESSION_COOKIE_NAME = "__Host-krtr_session"

SESSION_TOKEN_BYTES = 32  # 256 random bits; only their SHA-256 reaches the database.


class SessionConfig(BaseModel):
    """The time limits of a session.

    Exists so the service and its tests share the G15 numbers instead of repeating them.
    Consumed by `krtr/back/security/sessions/service.py`.
    """

    idle_timeout: timedelta = timedelta(minutes=5)
    absolute_timeout: timedelta = timedelta(minutes=30)
    token_refresh_margin: timedelta = timedelta(seconds=60)  # Refresh when less is left.
