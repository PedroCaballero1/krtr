"""Defines krtr-web's configuration.

Exists so the FastAPI app's environment-dependent behavior (interactive API
docs, where the built SPA lives) is read from the environment in exactly one
place instead of scattered `os.environ` lookups. Consumed by
`krtr/back/web/app.py`.
"""

import logging
import os
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel

logger = logging.getLogger(__name__)

DEFAULT_FRONTEND_DIST_DIR = Path("krtr/front/dist")


class WebEnvironment(StrEnum):
    """The deployment environment krtr-web is running in.

    Used to decide whether `/docs`, `/redoc` and `/openapi.json` are
    exposed (never in production, per task 4.1 of the guide) and any other
    environment-gated behavior. Consumed by `WebConfig`.
    """

    PRODUCTION = "production"
    DEVELOPMENT = "development"


class WebEnvironmentVariable(StrEnum):
    """The environment variables `WebConfig` reads from the environment.

    Centralizes the variable names so the config loader, the README and the
    tests never disagree on spelling. Consumed by `WebConfig.from_environment`.
    """

    ENVIRONMENT = "KRTR_WEB_ENVIRONMENT"
    FRONTEND_DIST_DIR = "KRTR_WEB_FRONTEND_DIST_DIR"


class WebConfig(BaseModel):
    """Configuration for the krtr-web FastAPI application.

    Exists to give `create_app` a validated, typed settings object instead
    of reading the environment inline. Consumed by `krtr/back/web/app.py`.
    """

    environment: WebEnvironment = WebEnvironment.PRODUCTION  # Fails closed: docs stay off
    # unless development is explicitly requested.
    frontend_dist_dir: Path = DEFAULT_FRONTEND_DIST_DIR

    @property
    def docs_enabled(self) -> bool:
        """Reports whether `/docs`, `/redoc` and `/openapi.json` should be exposed.

        Returns:
            bool: True outside of production; False in production.
        """
        return self.environment != WebEnvironment.PRODUCTION

    @classmethod
    def from_environment(cls) -> "WebConfig":
        """Builds a WebConfig from the environment, defaulting to production.

        Exists so the CLI and the app's module-level `app` instance get their
        settings without reading the environment themselves.

        Args:
            None.

        Returns:
            WebConfig: the resolved configuration.
        """
        settings: dict[str, str] = {}
        if environment := os.environ.get(WebEnvironmentVariable.ENVIRONMENT):
            settings["environment"] = environment
        if frontend_dist_dir := os.environ.get(WebEnvironmentVariable.FRONTEND_DIST_DIR):
            settings["frontend_dist_dir"] = frontend_dist_dir
        logger.debug("Loaded krtr-web configuration from the environment: %s", settings)
        return cls(**settings)
