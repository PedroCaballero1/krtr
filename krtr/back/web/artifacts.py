"""Defines the structured request/response contracts krtr-web's endpoints use.

Exists to keep an endpoint's request/response shape discoverable apart from
its implementation, per the §3.4 API contract in docs/guia-web-seguridad.md.
Consumed by `krtr/back/web/routers/`.
"""

from typing import Any, Literal

from pydantic import BaseModel

from krtr.back.security.audit.event_names import EventName


class HealthStatus(BaseModel):
    """The `GET /healthz` response contract.

    Exists so uptime checks (Cloud Run, GitHub Actions' smoke test) get a
    typed, stable shape. Returned by `krtr/back/web/routers/health.py`.
    """

    status: Literal["ok"] = "ok"


class RecordEventRequest(BaseModel):
    """The `POST /api/events` request body.

    Exists so the frontend can only submit an event name from the
    documented catalog (an invalid name fails validation with 422 before
    any handler code runs) and can never set `customer_id` itself — it is
    added server-side, from the session, once sessions exist (task 4.4).
    Consumed by `krtr/back/web/routers/events.py`.
    """

    event_name: EventName
    properties: dict[str, Any] = {}
