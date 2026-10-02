"""Defines krtr-web's security-headers middleware.

Exists to add the OWASP-recommended hardening headers (§4.2 of
docs/guia-web-seguridad.md) to every response from one place, instead of
each route handler setting them itself. Consumed by `krtr/back/web/app.py`.
"""

import logging
from typing import Awaitable, Callable

from fastapi import Request, Response

from krtr.back.security.headers.config import HeadersConfig

logger = logging.getLogger(__name__)

API_PATH_PREFIX = "/api/"

# Headers whose value never depends on configuration or the request.
STATIC_SECURITY_HEADERS: dict[str, str] = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "microphone=(self), camera=(), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}


def build_content_security_policy(auth_origin: str) -> str:
    """Builds the `Content-Security-Policy` header value.

    Exists so the policy's one environment-dependent piece — where the OIDC
    login form is allowed to submit to — is injected without duplicating the
    rest of the (otherwise static) policy.

    Args:
        auth_origin: Keycloak's origin (e.g.
            `https://<workspace>--krtr-auth.modal.run`), allowed in
            `form-action` alongside `'self'`.

    Returns:
        str: the full CSP header value.
    """
    return (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "img-src 'self' data:; "
        "media-src 'self' blob:; "
        "connect-src 'self'; "
        f"form-action 'self' {auth_origin}; "
        "frame-ancestors 'none'; "
        "base-uri 'none'; "
        "object-src 'none'"
    )


async def add_security_headers(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Adds the security headers to every response, and strips `Server`.

    Exists as HTTP middleware so no route needs to set these itself, and so
    a route can never accidentally omit them.

    Args:
        request: The incoming request, used to read `HeadersConfig` from
            `request.app.state.headers_config` and to gate `Cache-Control`
            on the `/api/*` prefix.
        call_next: The next handler in the middleware chain.

    Returns:
        Response: the downstream response, with security headers added and
        the `Server` header removed.
    """
    response = await call_next(request)
    config: HeadersConfig = request.app.state.headers_config

    for name, value in STATIC_SECURITY_HEADERS.items():
        response.headers[name] = value
    response.headers["Content-Security-Policy"] = build_content_security_policy(config.auth_origin)
    if request.url.path.startswith(API_PATH_PREFIX):
        response.headers["Cache-Control"] = "no-store"
    if "Server" in response.headers:
        del response.headers["Server"]

    return response
