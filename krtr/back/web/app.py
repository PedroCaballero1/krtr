"""Builds the krtr-web FastAPI application.

Exists as the single place that assembles the app: configuration,
middleware, routers and the built SPA. Consumed by `krtr/cli/back/web/handler.py`
(`krtr back web serve`) and by `tests/back/web/test_app.py` via `create_app`.
"""

import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from krtr.back.security.headers.config import HeadersConfig
from krtr.back.security.headers.middleware import add_security_headers
from krtr.back.web.config import WebConfig
from krtr.back.web.middleware import log_request
from krtr.back.web.routers.health import health_router
from krtr.back.web.routers.spa import spa_router

logger = logging.getLogger(__name__)


def create_app(
    config: WebConfig | None = None, headers_config: HeadersConfig | None = None
) -> FastAPI:
    """Builds and configures the krtr-web FastAPI application.

    Exists so the app is assembled the same way whether it is run via
    `krtr back web serve`, imported by uvicorn in Docker/Cloud Run, or built
    in a test with a custom `WebConfig`/`HeadersConfig`.

    Args:
        config: The configuration to build the app with. When None, it is
            loaded from the environment via `WebConfig.from_environment`.
        headers_config: The security-headers configuration. When None, it is
            loaded from the environment via `HeadersConfig.from_environment`.

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
    app.middleware("http")(add_security_headers)
    app.middleware("http")(log_request)
    app.include_router(health_router)
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
