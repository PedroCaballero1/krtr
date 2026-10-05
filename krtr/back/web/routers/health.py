"""Defines the `GET /healthz` route.

Exists as the single liveness/readiness check for krtr-web, used by the
GitHub Actions deploy smoke test (task 6.7 of docs/guia-web-seguridad_modal.md).
Consumed by `krtr/back/web/app.py`, which includes `health_router`.
"""

from fastapi import APIRouter

from krtr.back.web.artifacts import HealthStatus

health_router = APIRouter()


@health_router.get("/healthz", include_in_schema=False)
async def get_health() -> HealthStatus:
    """Reports that the app process is up and able to serve requests.

    Exists so infrastructure (the deploy smoke test, uptime checks) can
    check liveness without hitting an authenticated or database-backed route.

    Args:
        None.

    Returns:
        HealthStatus: always `{"status": "ok"}` when the process responds.
    """
    return HealthStatus()
