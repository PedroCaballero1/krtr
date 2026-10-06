"""Builds the krtr-web FastAPI application.

Exists as the single place that assembles the app: configuration,
middleware, routers and the built SPA. `create_served_app` is the factory
`krtr back web serve` (`krtr/cli/back/web/handler.py`) hands to uvicorn;
tests build the app with `create_app` and their own collaborators.
"""

import logging

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from krtr.back.ia.messages.store import InMemoryMessageStore, MessageStore, NeonMessageStore
from krtr.back.security.audit.middleware import record_http_request
from krtr.back.security.audit.recorder import EventRecorder
from krtr.back.security.crypto.cipher import AesGcmCipher
from krtr.back.security.crypto.config import CryptoConfig, CryptoEnvironmentVariable
from krtr.back.security.csrf.config import CsrfConfig
from krtr.back.security.headers.config import HeadersConfig
from krtr.back.security.headers.middleware import add_security_headers
from krtr.back.security.oidc.client import KeycloakOidcClient
from krtr.back.security.oidc.config import OidcConfig
from krtr.back.security.oidc.login_cookie import LoginCookieCodec
from krtr.back.security.rate_limit.config import RateLimitConfig
from krtr.back.security.sessions.service import SessionService
from krtr.back.security.sessions.store import SessionStore
from krtr.back.web.cases.repository import CaseRepository, StubCaseRepository
from krtr.back.web.chat.agent import build_agent_responder
from krtr.back.web.chat.responder import ChatResponder, StubChatResponder
from krtr.back.web.config import WebConfig, WebEnvironment
from krtr.back.web.csrf import register_csrf_error_handler
from krtr.back.web.dependencies import AuthServices, register_auth_error_handlers
from krtr.back.web.middleware import limit_request_size, log_request
from krtr.back.web.rate_limit import (
    RateLimiters,
    enforce_rate_limits,
    register_rate_limit_error_handler,
)
from krtr.back.web.routers.auth import auth_router
from krtr.back.web.routers.cases import cases_router
from krtr.back.web.routers.chat import chat_router
from krtr.back.web.routers.events import events_router
from krtr.back.web.routers.health import health_router
from krtr.back.web.routers.session import session_router
from krtr.back.web.routers.spa import spa_router
from krtr.database.neon.client import NeonClient
from krtr.database.neon.config import NeonConfig

logger = logging.getLogger(__name__)

KEYCLOAK_TIMEOUT_SECONDS = 10  # A login or refresh must not hang a worker on Keycloak.


def create_app(
    config: WebConfig | None = None,
    headers_config: HeadersConfig | None = None,
    event_recorder: EventRecorder | None = None,
    auth_services: AuthServices | None = None,
    csrf_config: CsrfConfig | None = None,
    case_repository: CaseRepository | None = None,
    chat_responder: ChatResponder | None = None,
    rate_limit_config: RateLimitConfig | None = None,
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
        auth_services: The OIDC login and session services (tasks 4.3, 4.4).
            When None, the login and session routes answer 503;
            `create_served_app` always provides them in production.
        csrf_config: The origin state-changing requests must come from (task 4.5). When
            None, it is loaded from the environment via `CsrfConfig.from_environment`.
        case_repository: Where the customers' cases live (task 4.8). When None, an
            in-memory `StubCaseRepository` with sample cases.
        chat_responder: Who answers chat messages (task 4.9). When None, the D15
            placeholder (`StubChatResponder`); `create_served_app` passes the engine.
        rate_limit_config: The request limits (task 4.6). When None, the defaults.

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
    app.state.auth_services = auth_services
    app.state.csrf_config = csrf_config or CsrfConfig.from_environment()
    app.state.case_repository = case_repository or StubCaseRepository()
    app.state.chat_responder = chat_responder or StubChatResponder()
    app.state.rate_limiters = RateLimiters.from_config(rate_limit_config or RateLimitConfig())
    _add_middleware(app)
    register_auth_error_handlers(app)
    register_csrf_error_handler(app)
    register_rate_limit_error_handler(app)
    routers = (health_router, events_router, auth_router, session_router, cases_router)
    for router in (*routers, chat_router):
        app.include_router(router)
    _mount_frontend_assets(app, resolved_config)
    app.include_router(spa_router)
    logger.info("krtr-web app created (environment=%s)", resolved_config.environment)
    return app


def _add_middleware(app: FastAPI) -> None:
    """Adds krtr-web's HTTP middleware, outermost last.

    Order, from the outside in: the request_id log, the `http_request` event, the security
    headers, the request limits (task 4.6), and the body size limit. Limits run inside the
    first three, so a 429 or 413 is still logged, recorded and sent with the security headers.

    Args:
        app: The app to add them to.

    Returns:
        None.
    """
    for middleware in (
        limit_request_size,
        enforce_rate_limits,
        add_security_headers,
        record_http_request,
        log_request,
    ):
        app.middleware("http")(middleware)


def create_served_app() -> FastAPI:
    """Builds the app that is actually served, with event recording and login wired in.

    Exists because `create_app` leaves its collaborators optional, so tests
    can inject their own, while the served app must record every event
    (G21) and log customers in (tasks 4.3, 4.4). Used as uvicorn's factory by
    `krtr back web serve`, and meant to be served the same way on Modal.
    `.env` is loaded first, so a local run reads the same variables the
    Modal secret provides in production.

    Args:
        None.

    Returns:
        FastAPI: the configured application, recording events and logging
        customers in when its environment provides their settings.

    Raises:
        ValueError: in production, if any of those settings is missing or invalid.
    """
    load_dotenv()
    config = WebConfig.from_environment()
    return create_app(
        config,
        event_recorder=_build_event_recorder(config),
        auth_services=_build_auth_services(config),
        chat_responder=_build_chat_responder(config),
    )


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


def _build_auth_services(config: WebConfig) -> AuthServices | None:
    """Builds the login and session services from the environment; mandatory in production.

    Exists so production fails fast without a working login, while local
    development can run without Keycloak (the login routes then answer 503).
    The settings and the key are checked before any connection is opened.

    Args:
        config: The resolved WebConfig, whose environment decides whether a
            missing or invalid setting stops the app.

    Returns:
        AuthServices | None: the services, or None outside production when the
        environment cannot build them.

    Raises:
        ValueError: in production, naming the setting that is missing or invalid.
    """
    try:
        oidc_config = OidcConfig.from_environment()
        tokens_key = CryptoConfig.from_environment(CryptoEnvironmentVariable.TOKENS_KEY)
        neon_client = NeonClient()
    except ValueError as error:
        if config.environment == WebEnvironment.PRODUCTION:
            raise ValueError(f"krtr-web cannot start without login: {error}") from error
        logger.warning("Login is off (environment=%s): %s", config.environment, error)
        return None
    cipher = AesGcmCipher(tokens_key.decoded_key())
    oidc_client = KeycloakOidcClient(oidc_config, httpx.Client(timeout=KEYCLOAK_TIMEOUT_SECONDS))
    session_service = SessionService(SessionStore(neon_client, cipher), oidc_client)
    logger.info("Login is on (Keycloak at %s)", oidc_config.auth_origin)
    return AuthServices(
        oidc_client=oidc_client,
        login_codec=LoginCookieCodec(cipher),
        session_service=session_service,
    )


def _build_chat_responder(config: WebConfig) -> ChatResponder:
    """Builds the chat over the conversation engine and Neon; mandatory in production.

    Exists so production answers with the engine and keeps every message (G17, G21), while
    local development can run without Neon (the D15 placeholder answers instead).

    Args:
        config: The resolved WebConfig, whose environment decides whether a missing setting
            stops the app.

    Returns:
        ChatResponder: the engine-backed responder, or the placeholder outside production when
        Neon is not configured.

    Raises:
        ValueError: in production, if NEON_DB_HOST or KRTR_MESSAGES_KEY is missing or invalid.
    """
    try:
        neon_config = NeonConfig.from_environment()
        messages = _build_message_store(config)
    except ValueError as error:
        if config.environment == WebEnvironment.PRODUCTION:
            raise ValueError(f"krtr-web cannot start without the chat: {error}") from error
        logger.warning(
            "The chat answers the placeholder (environment=%s): %s", config.environment, error
        )
        return StubChatResponder()
    return build_agent_responder(NeonClient(neon_config), messages)


def _build_message_store(config: WebConfig) -> MessageStore:
    """Builds the `messages` store; outside production, falls back to memory without the key.

    Args:
        config: The resolved WebConfig.

    Returns:
        MessageStore: the Neon store, or an in-memory one in development without the key.

    Raises:
        ValueError: in production, if KRTR_MESSAGES_KEY or NEON_DB_HOST is missing or invalid.
    """
    try:
        return NeonMessageStore.from_environment()
    except ValueError as error:
        if config.environment == WebEnvironment.PRODUCTION:
            raise
        logger.warning("Chat messages are kept in memory only: %s", error)
        return InMemoryMessageStore()


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
