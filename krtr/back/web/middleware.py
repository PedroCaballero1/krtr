"""Defines krtr-web's request-scoped logging middleware.

Exists to give every request a `request_id` and a one-line start/end log
entry, per §3.4 of docs/guia-web-seguridad.md ("Todas las respuestas llevan
un request_id"). Consumed by `krtr/back/web/app.py`.
"""

import logging
import time
from typing import Awaitable, Callable
from uuid import uuid4

from fastapi import Request, Response

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-Id"


async def log_request(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Assigns a request_id to the request and logs its start and completion.

    Exists so every request is traceable end-to-end (logs, error responses,
    the `X-Request-Id` response header) without each route handler doing it
    itself. Registered as HTTP middleware in `create_app`.

    Args:
        request: The incoming request.
        call_next: The next handler in the middleware chain.

    Returns:
        Response: the downstream response, with the request_id header added.
    """
    request_id = str(uuid4())
    request.state.request_id = request_id
    started_at = time.perf_counter()
    logger.info("Handling %s %s (request_id=%s)", request.method, request.url.path, request_id)

    response = await call_next(request)

    duration_ms = (time.perf_counter() - started_at) * 1000
    response.headers[REQUEST_ID_HEADER] = request_id
    logger.info(
        "Completed %s %s -> %d in %.1fms (request_id=%s)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        request_id,
    )
    return response
