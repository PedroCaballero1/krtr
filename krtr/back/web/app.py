"""Builds the krtr-web FastAPI application.

Exists as the single place that assembles the app: configuration,
middleware, routers and the built SPA. `create_served_app` is the factory
`krtr back web serve` (`krtr/cli/back/web/handler.py`) hands to uvicorn;
tests build the app with `create_app` and their own collaborators.
"""

import logging

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from krtr.back.security.audit.middleware import record_http_request
from krtr.back.security.audit.recorder import EventRecorder
from krtr.back.security.headers.config import HeadersConfig
from krtr.back.security.headers.middleware import add_security_headers
from krtr.back.web.config import WebConfig, WebEnvironment
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
            None, event recording is skipped (logged, not an error).
            `create_served_app` always provides one in production; tests
            may omit it.

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


def create_served_app() -> FastAPI:
    """Builds the app that is actually served, with event recording wired in.

    Exists because `create_app` leaves the event recorder optional, so tests
    can inject their own, while the served app must record every event
    (G21). Used as uvicorn's factory by `krtr back web serve`, and meant to
    be served the same way on Modal. `.env` is loaded first, so a local run
    reads the same variables the Modal secret provides in production.

    Args:
        None.

    Returns:
        FastAPI: the configured application, recording events when its
        environment provides `KRTR_EVENTS_KEY` and `NEON_DB_HOST`.

    Raises:
        ValueError: in production, if either variable is missing or invalid.
    """
    load_dotenv()
    config = WebConfig.from_environment()
    return create_app(config, event_recorder=_build_event_recorder(config))


def _build_event_recorder(config: WebConfig) -> EventRecorder | None:
    """Builds the event recorder from the environment; mandatory in production.

    Exists so production fails fast instead of silently dropping every
    event, while local development can still run without Neon or a key.

    Args:
        config: The resolved WebConfig, whose environment decides whether a
            missing or invalid variable stops the app.

    Returns:
        EventRecorder | None: the recorder, or None outside production when
        the environment cannot build one.

    Raises:
        ValueError: in production, naming the variable that is missing or invalid.
    """
    try:
        recorder = EventRecorder.from_environment()
    except ValueError as error:
        if config.environment == WebEnvironment.PRODUCTION:
            raise ValueError(f"krtr-web cannot start without event recording: {error}") from error
        logger.warning("Event recording is off (environment=%s): %s", config.environment, error)
        return None
    logger.info("Event recording is on")
    return recorder


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
