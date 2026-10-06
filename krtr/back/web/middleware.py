"""Defines krtr-web's request-scoped middleware: logging and the body size limit.

Exists to give every request a `request_id` and a one-line start/end log
entry, per §3.4 of docs/guia-web-seguridad_modal.md ("Todas las respuestas llevan
un request_id"), and to refuse oversized bodies before anything reads them.
Consumed by `krtr/back/web/app.py`.
"""

import logging
import time
from typing import Awaitable, Callable
from uuid import uuid4

from fastapi import Request, Response

from krtr.back.web.chat.audio import MAX_AUDIO_BYTES
from krtr.back.web.errors import ApiErrorCode, MessageKey, api_error

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-Id"
# The largest body any route needs: a 2 MB voice note plus its multipart framing.
MAX_REQUEST_BYTES = MAX_AUDIO_BYTES + 64 * 1024


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


async def limit_request_size(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Answers 413 to a request whose declared body is larger than any route accepts.

    Exists because FastAPI parses a multipart body (spooling files to disk) before a route or
    its session check runs, so without this an anonymous client could make the server store
    arbitrarily large uploads. The voice route still counts the bytes it reads.

    Args:
        request: The incoming request.
        call_next: The next handler in the middleware chain.

    Returns:
        Response: 413 for an oversized or unreadable Content-Length; the downstream response
        otherwise.
    """
    declared = request.headers.get("content-length")
    if declared is not None and (not declared.isdigit() or int(declared) > MAX_REQUEST_BYTES):
        logger.warning("Refused a %s-byte body on %s", declared, request.url.path)
        return api_error(413, ApiErrorCode.REQUEST_TOO_LARGE, MessageKey.REQUEST_TOO_LARGE)
    return await call_next(request)
