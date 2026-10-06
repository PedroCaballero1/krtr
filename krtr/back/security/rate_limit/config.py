"""Defines krtr-web's request limits (task 4.6, G3, D6).

Exists so the three limits and their window are declared once: the chat's 20 messages per
minute per customer (G3), a moderate limit per session on `/api/*`, and 600 requests per
minute per IP on the whole site (D6, which Cloud Armor would have applied before the move to
Modal). Consumed by `krtr/back/web/rate_limit.py`.
"""

from datetime import timedelta
from enum import StrEnum

from pydantic import BaseModel


class LimitScope(StrEnum):
    """What a limit counts requests by, as recorded in `rate_limit_exceeded`."""

    IP = "ip"  # The connecting address, `request.client.host` (0.4a), never a header.
    SESSION = "session"  # The session cookie, on /api/*.
    CHAT = "chat"  # The session's customer, on /api/chat/*.


class RateLimitConfig(BaseModel):
    """The limits, each a number of requests per `window`.

    Exists to give the limiters a validated, typed settings object. The per-session limit is
    generous enough for the SPA's own polling and events, and low enough to stop a script.
    Consumed by `krtr/back/web/app.py`.
    """

    window: timedelta = timedelta(minutes=1)
    per_ip: int = 600
    per_session: int = 240
    chat_per_customer: int = 20
