"""Defines the middleware that records an `http_request` event per request.

Exists so every request is audited (G21) without each route handler doing
it itself. The write happens in a `BackgroundTask`, scheduled after the
response is built, so recording an event never adds latency to the
response the caller sees. Consumed by `krtr/back/web/app.py`.
"""

import logging
import time
from typing import Awaitable, Callable

from fastapi import Request, Response
from starlette.background import BackgroundTask

from krtr.back.security.audit.event_names import EventName
from krtr.back.security.audit.recorder import EventRecorder

logger = logging.getLogger(__name__)


async def record_http_request(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Times the request and schedules an `http_request` event after it responds.

    Exists as HTTP middleware so the event's properties (status, latency)
    can only be known once the response exists, while still never blocking
    the response on the database write.

    Args:
        request: The incoming request.
        call_next: The next handler in the middleware chain.

    Returns:
        Response: the downstream response, with a background task attached
        that records the `http_request` event.
    """
    started_at = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - started_at) * 1000

    recorder: EventRecorder | None = getattr(request.app.state, "event_recorder", None)
    if recorder is None:
        logger.debug("No event recorder configured; skipping http_request event")
        return response

    properties = _build_request_properties(request, response, duration_ms)
    response.background = BackgroundTask(recorder.record_event, EventName.HTTP_REQUEST, properties)
    return response


def _build_request_properties(request: Request, response: Response, duration_ms: float) -> dict:
    """Builds the `http_request` event's properties from a completed exchange.

    Args:
        request: The incoming request.
        response: The response about to be sent.
        duration_ms: How long the request took to handle, in milliseconds.

    Returns:
        dict: the properties to record, per §3.5's `http_request` shape.
    """
    return {
        "method": request.method,
        "path": request.url.path,
        "status": response.status_code,
        "latency_ms": round(duration_ms, 1),
        "ip": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
        "request_id": getattr(request.state, "request_id", None),
    }
