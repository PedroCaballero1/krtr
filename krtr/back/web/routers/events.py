"""Defines the `POST /api/events` route.

Exists so the frontend can report UI events (§3.5's catalog) through the one
endpoint the guide's §3.4 contract defines, instead of talking to the
database directly. Consumed by `krtr/back/web/app.py`.
"""

import json
import logging

from fastapi import APIRouter, HTTPException, Request, Response
from starlette.background import BackgroundTask

from krtr.back.security.audit.recorder import EventRecorder
from krtr.back.web.artifacts import RecordEventRequest

logger = logging.getLogger(__name__)

events_router = APIRouter()

MAX_PROPERTIES_BYTES = 4096


@events_router.post("/api/events", status_code=202, include_in_schema=False)
async def record_event(payload: RecordEventRequest, request: Request) -> Response:
    """Accepts a frontend-originated event and records it in the background.

    Exists so the frontend's `trackEvent` (task 5.3) has one endpoint to
    call for every UI event; `event_name` is already validated against the
    `EventName` catalog by `RecordEventRequest` (an unknown name never
    reaches this function — FastAPI returns 422 first).

    Args:
        payload: The event name and properties, from the request body.
        request: The current request, used to read the configured
            `EventRecorder` from `request.app.state.event_recorder`.

    Returns:
        Response: 202 Accepted, with the write scheduled as a background
        task so it never adds latency to this response.

    Raises:
        HTTPException: 413 if `properties`, serialized to JSON, exceeds
            `MAX_PROPERTIES_BYTES`.
    """
    serialized_properties = json.dumps(payload.properties, sort_keys=True).encode("utf-8")
    if len(serialized_properties) > MAX_PROPERTIES_BYTES:
        raise HTTPException(
            status_code=413, detail=f"properties exceeds {MAX_PROPERTIES_BYTES} bytes"
        )

    recorder: EventRecorder | None = getattr(request.app.state, "event_recorder", None)
    if recorder is None:
        logger.warning("No event recorder configured; dropping event %s", payload.event_name)
        return Response(status_code=202)

    background = BackgroundTask(recorder.record_event, payload.event_name, payload.properties)
    return Response(status_code=202, background=background)
