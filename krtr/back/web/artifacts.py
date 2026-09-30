"""Defines the structured response contracts krtr-web's endpoints return.

Exists to keep an endpoint's response shape discoverable apart from its
implementation, per the §3.4 API contract in docs/guia-web-seguridad.md.
Consumed by `krtr/back/web/routers/`.
"""

from typing import Literal

from pydantic import BaseModel


class HealthStatus(BaseModel):
    """The `GET /healthz` response contract.

    Exists so uptime checks (Cloud Run, GitHub Actions' smoke test) get a
    typed, stable shape. Returned by `krtr/back/web/routers/health.py`.
    """

    status: Literal["ok"] = "ok"
