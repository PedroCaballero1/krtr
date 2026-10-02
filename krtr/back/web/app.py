"""Builds the krtr-web FastAPI application.

Exists as the single place that assembles the app: configuration,
middleware, routers and the built SPA. Consumed by `krtr/cli/back/web/handler.py`
(`krtr back web serve`) and by `tests/back/web/test_app.py` via `create_app`.
"""

import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from krtr.back.security.audit.middleware import record_http_request
from krtr.back.security.audit.recorder import EventRecorder
from krtr.back.security.headers.config import HeadersConfig
from krtr.back.security.headers.middleware import add_security_headers
from krtr.back.web.config import WebConfig
from krtr.back.web.middleware import log_request
from krtr.back.web.routers.events import events_router
from krtr.back.web.routers.health import health_router
from krtr.back.web.routers.spa import spa_router

logger = logging.getLogger(__name__)


def create_app(
    config: WebConfig | None = None,
    headers_config: HeadersConfig | None = None,
    event_recorder: EventRecorder | None = None,
) -> FastAPI:
    """Builds and configures the krtr-web FastAPI application.

    Exists so the app is assembled the same way whether it is run locally
    via `krtr back web serve`, served by the `web` function on Modal, or
    built in a test with custom configuration.

    Args:
        config: The configuration to build the app with. When None, it is
            loaded from the environment via `WebConfig.from_environment`.
        headers_config: The security-headers configuration. When None, it is
            loaded from the environment via `HeadersConfig.from_environment`.
        event_recorder: The recorder used to write audit events (G21). When
            None, event recording is skipped (logged, not an error) — the
            deployed app is expected to always provide one once Neon (task
            1.3) and the encryption key (`KRTR_EVENTS_KEY`) exist; tests may
            omit it.

    Returns:
        FastAPI: the configured application, ready to serve.
    """
    resolved_config = config or WebConfig.from_environment()
    resolved_headers_config = headers_config or HeadersConfig.from_environment()
    app = FastAPI(
        title="krtr",
        docs_url="/docs" if resolved_config.docs_enabled else None,
        redoc_url="/redoc" if resolved_config.docs_enabled else None,
        openapi_url="/openapi.json" if resolved_config.docs_enabled else None,
    )
    app.state.config = resolved_config
    app.state.headers_config = resolved_headers_config
    app.state.event_recorder = event_recorder
    app.middleware("http")(add_security_headers)
    app.middleware("http")(record_http_request)
    app.middleware("http")(log_request)
    app.include_router(health_router)
    app.include_router(events_router)
    _mount_frontend_assets(app, resolved_config)
    app.include_router(spa_router)
    logger.info("krtr-web app created (environment=%s)", resolved_config.environment)
    return app


def _mount_frontend_assets(app: FastAPI, config: WebConfig) -> None:
    """Mounts the built SPA's static assets directory, if it exists.

    Exists so `create_app` stays a short assembly sequence; the frontend not
    having been built yet (e.g. before task 5.1) never crashes the backend.

    Args:
        app: The FastAPI application to mount the assets onto.
        config: The resolved WebConfig, providing `frontend_dist_dir`.

    Returns:
        None.
    """
    assets_dir = config.frontend_dist_dir / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")
        logger.info("Mounted frontend assets from %s", assets_dir)
    else:
        logger.warning(
            "Frontend assets not found at %s; the SPA will 404 until it is built", assets_dir
        )


app = create_app()
