"""Schedules audit events from krtr-web's routes (G21).

Exists so a route records an event (e.g. `auth_login_succeeded`) with one call that runs after
the response is sent, adding no latency, and that is skipped (with a debug log) when the app
has no recorder, as in tests. Consumed by the auth router and `krtr/back/web/dependencies.py`.
"""

import logging
from typing import Any

from fastapi import BackgroundTasks, Request

from krtr.back.security.audit.event_names import EventName
from krtr.back.security.audit.recorder import EventRecorder

logger = logging.getLogger(__name__)


def schedule_event(
    request: Request, tasks: BackgroundTasks, event_name: EventName, properties: dict[str, Any]
) -> None:
    """Queues one event to be recorded after the response.

    Args:
        request: The current request, to reach the app's recorder.
        tasks: The response's background tasks.
        event_name: The event, from the catalog.
        properties: Its properties; never passwords, tokens or cookies.

    Returns:
        None.
    """
    recorder: EventRecorder | None = getattr(request.app.state, "event_recorder", None)
    if recorder is None:
        logger.debug("No event recorder configured; skipping %s", event_name.value)
        return
    tasks.add_task(recorder.record_event, event_name, properties)
