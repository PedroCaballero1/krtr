"""Applies krtr-web's request limits and answers 429 when one is exceeded (task 4.6).

Exists because there is no WAF in front of Modal: every limit lives in the app.

- `enforce_rate_limits` (middleware): 600 requests per minute per IP on the whole site, and the
  per-session limit on `/api/*`. The IP is `request.client.host`, the address Modal connects
  from (0.4a); `X-Forwarded-For`, `X-Real-IP` and `Forwarded` are never read, so a client
  cannot spoof its way past the limit.
- `require_chat_session` (dependency): 20 chat messages per minute per customer (G3), counted
  only once the session and CSRF checks pass.

Every rejection answers 429 with `Retry-After` and records `rate_limit_exceeded`. Consumed by
`krtr/back/web/app.py` and `krtr/back/web/routers/chat.py`.
"""

import hashlib
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from fastapi import BackgroundTasks, Depends, FastAPI, Request, Response
from fastapi.responses import JSONResponse

from krtr.back.security.audit.event_names import EventName
from krtr.back.security.rate_limit.config import LimitScope, RateLimitConfig
from krtr.back.security.rate_limit.errors import RateLimited
from krtr.back.security.rate_limit.limiter import SlidingWindowLimiter
from krtr.back.security.sessions.artifacts import SessionRecord
from krtr.back.security.sessions.config import SESSION_COOKIE_NAME
from krtr.back.web.auditing import schedule_event
from krtr.back.web.csrf import require_session_with_csrf
from krtr.back.web.errors import ApiErrorCode, MessageKey, api_error

logger = logging.getLogger(__name__)

API_PREFIX = "/api/"
UNKNOWN_CLIENT = "unknown"  # No peer address (only in-process test clients).

# The i18n key of each scope's 429: the chat shows its own message (chat_error_rate_limited).
_MESSAGE_KEYS = {
    LimitScope.IP: MessageKey.RATE_LIMITED,
    LimitScope.SESSION: MessageKey.RATE_LIMITED,
    LimitScope.CHAT: MessageKey.CHAT_RATE_LIMITED,
}


@dataclass(frozen=True)
class RateLimiters:
    """The app's three limiters, one per scope.

    Exists so the app holds them as one unit, built once from `RateLimitConfig`.
    Consumed through `request.app.state.rate_limiters`.
    """

    per_ip: SlidingWindowLimiter
    per_session: SlidingWindowLimiter
    chat_per_customer: SlidingWindowLimiter

    @classmethod
    def from_config(cls, config: RateLimitConfig) -> "RateLimiters":
        """Builds the three limiters from the configured limits.

        Args:
            config: The limits and their window.

        Returns:
            RateLimiters: fresh limiters with no hits.
        """
        return cls(
            per_ip=SlidingWindowLimiter(LimitScope.IP, config.per_ip, config.window),
            per_session=SlidingWindowLimiter(LimitScope.SESSION, config.per_session, config.window),
            chat_per_customer=SlidingWindowLimiter(
                LimitScope.CHAT, config.chat_per_customer, config.window
            ),
        )


async def enforce_rate_limits(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Counts the request against its IP and, on /api/*, its session; 429 when over a limit.

    Args:
        request: The incoming request.
        call_next: The next handler in the middleware chain.

    Returns:
        Response: 429 when a limit is exceeded; the downstream response otherwise.
    """
    limiters: RateLimiters = request.app.state.rate_limiters
    try:
        limiters.per_ip.hit(request.client.host if request.client else UNKNOWN_CLIENT)
        session_token = request.cookies.get(SESSION_COOKIE_NAME)
        if request.url.path.startswith(API_PREFIX) and session_token:
            limiters.per_session.hit(_session_key(session_token))
    except RateLimited as error:
        return rate_limited_response(request, error)
    return await call_next(request)


def require_chat_session(
    request: Request, session: SessionRecord = Depends(require_session_with_csrf)
) -> SessionRecord:
    """Returns the live session once its customer is within the chat's 20 messages per minute.

    Args:
        request: The current request.
        session: The request's live session, past the CSRF checks.

    Returns:
        SessionRecord: the live session.

    Raises:
        RateLimited: if the customer already sent 20 messages in the last minute.
    """
    limiters: RateLimiters = request.app.state.rate_limiters
    limiters.chat_per_customer.hit(session.customer_id)
    return session


async def handle_rate_limited(request: Request, error: RateLimited) -> JSONResponse:
    """Answers a request over its limit (raised by a dependency).

    Args:
        request: The rejected request.
        error: Which limit, and how long to wait.

    Returns:
        JSONResponse: 429 with `Retry-After`.
    """
    return rate_limited_response(request, error)


def rate_limited_response(request: Request, error: RateLimited) -> JSONResponse:
    """Builds the 429 for an exceeded limit and records `rate_limit_exceeded`.

    Args:
        request: The rejected request.
        error: Which limit, and how long to wait.

    Returns:
        JSONResponse: 429 with the §3.4 body and `Retry-After` in seconds.
    """
    logger.warning("Rate limit (%s) exceeded on %s", error.scope.value, request.url.path)
    response = api_error(429, ApiErrorCode.RATE_LIMITED, _MESSAGE_KEYS[error.scope])
    response.headers["Retry-After"] = str(error.retry_after_seconds)
    tasks = BackgroundTasks()
    properties = {
        "scope": error.scope.value,
        "path": request.url.path,
        "retry_after_seconds": error.retry_after_seconds,
    }
    schedule_event(request, tasks, EventName.RATE_LIMIT_EXCEEDED, properties)
    response.background = tasks
    return response


def register_rate_limit_error_handler(app: FastAPI) -> None:
    """Registers the handler that turns a limit raised by a dependency into a 429.

    Args:
        app: The app to register it on.

    Returns:
        None.
    """
    app.add_exception_handler(RateLimited, handle_rate_limited)


def _session_key(session_token: str) -> str:
    """Derives the per-session key from the session cookie, without keeping the token.

    Args:
        session_token: The session cookie's value.

    Returns:
        str: the token's SHA-256, in hex.
    """
    return hashlib.sha256(session_token.encode()).hexdigest()
