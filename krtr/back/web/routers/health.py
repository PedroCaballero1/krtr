"""Defines the `GET /healthz` route.

Exists as the single liveness/readiness check for krtr-web, used by Cloud
Run's health probe and the GitHub Actions deploy smoke test (§6.8 of the
guide). Consumed by `krtr/back/web/app.py`, which includes `health_router`.
"""

from fastapi import APIRouter

from krtr.back.web.artifacts import HealthStatus

health_router = APIRouter()


@health_router.get("/healthz", include_in_schema=False)
async def get_health() -> HealthStatus:
    """Reports that the app process is up and able to serve requests.

    Exists so infrastructure (Cloud Run, CI) can check liveness without
    hitting an authenticated or database-backed route.

    Args:
        None.

    Returns:
        HealthStatus: always `{"status": "ok"}` when the process responds.
    """
    return HealthStatus()
