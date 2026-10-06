"""Publishes Keycloak on Modal while hiding its admin and operational endpoints (task 3.7, D19).

Exists because Modal has no WAF or IP rules to restrict `/admin`: Keycloak listens on
`127.0.0.1:8081` inside the `auth` container, and this ASGI app is what Modal exposes. It:

- answers 404, without reaching Keycloak, to `/admin/*`, `/realms/master/*`, `/metrics` and
  `/health*`. The path is normalized first (repeated slashes, `.`/`..` segments, `;` parameters,
  letter case), and Keycloak receives exactly the normalized path that was checked, so no
  spelling of a blocked path gets through;
- forwards everything else with its method, body, query, headers and cookies, and returns
  Keycloak's answer unchanged: status (redirects are not followed), every `Set-Cookie`, body;
- sets `X-Forwarded-Proto`, `X-Forwarded-Host`, `X-Forwarded-Port` and `X-Forwarded-For`
  itself, from the connection, and drops whatever the client sent in those and in `Forwarded`
  and `X-Real-IP`, which Modal passes through untouched (0.4a);
- adds the hardening headers of `krtr/back/security/headers/` that Keycloak does not set, and
  removes `Server`;
- answers 504 when Keycloak is too slow and 502 when it is unreachable.

Consumed by the `auth` function of `krtr/back/deploy/app.py` (task 6.3).
"""

import logging
import posixpath
from urllib.parse import quote

import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

from krtr.back.security.headers.middleware import STATIC_SECURITY_HEADERS
from krtr.back.security.keycloak.config import GatewayConfig

logger = logging.getLogger(__name__)

# Paths the internet must never reach (D19), compared after normalization, in lowercase:
# each of these and everything below it, and any path starting with `/health`.
BLOCKED_PATHS = ("/admin", "/realms/master", "/metrics")
BLOCKED_PATH_START = "/health"

# Headers the gateway sets itself, or that only describe one hop; never copied from the client.
_DROPPED_REQUEST_HEADERS = frozenset(
    {
        "host",
        "content-length",
        "accept-encoding",  # Replaced by `identity`; see `_forwarded_headers`.
        "forwarded",
        "x-forwarded-for",
        "x-forwarded-host",
        "x-forwarded-proto",
        "x-forwarded-port",
        "x-forwarded-prefix",
        "x-real-ip",
        "connection",
        "keep-alive",
        "proxy-authorization",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
    }
)
# `content-encoding` goes too: httpx always hands over the decoded body, so a `gzip` label left on
# it would make the browser fail to decode the stylesheets and scripts of the login page.
_DROPPED_RESPONSE_HEADERS = frozenset(
    {
        "server",
        "content-length",
        "content-encoding",
        "connection",
        "keep-alive",
        "transfer-encoding",
        "trailer",
    }
)
_ALL_METHODS = ["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]


def normalize_path(path: str) -> str:
    """Reduces a request path to the one form both the blocklist and Keycloak see.

    Args:
        path: The request's percent-decoded path.

    Returns:
        str: the path without `;` parameters, repeated slashes or dot segments, starting with
        `/`; a trailing slash is kept, since Keycloak's pages can depend on it.
    """
    segments = [segment.split(";", 1)[0] for segment in path.split("/")]
    joined = "/" + "/".join(segment for segment in segments if segment)
    normalized = posixpath.normpath(joined)
    normalized = "/" + normalized.lstrip("/")
    if path.endswith("/") and normalized != "/":
        normalized += "/"
    return normalized


def is_blocked(normalized_path: str) -> bool:
    """Reports whether a normalized path is one of the hidden endpoints.

    Args:
        normalized_path: The output of `normalize_path`.

    Returns:
        bool: True for `/admin`, `/realms/master`, `/metrics`, `/health` and anything below them.
    """
    lowered = normalized_path.lower()
    if lowered.startswith(BLOCKED_PATH_START):
        return True
    trimmed = lowered.rstrip("/")
    return any(trimmed == blocked or trimmed.startswith(f"{blocked}/") for blocked in BLOCKED_PATHS)


class KeycloakGateway:
    """Forwards requests to the local Keycloak, except the hidden endpoints.

    Exists as the state behind the gateway's single route: its settings and one HTTP client
    reused for every request. Consumed by `build_gateway`.
    """

    def __init__(self, config: GatewayConfig, client: httpx.AsyncClient) -> None:
        """Builds the gateway.

        Args:
            config: Where Keycloak listens, and the public host it is served as.
            client: The HTTP client that talks to Keycloak; it must not follow redirects.
        """
        self._config = config
        self._client = client

    async def handle(self, request: Request) -> Response:
        """Answers one request: 404 for a hidden endpoint, Keycloak's answer otherwise.

        Args:
            request: The incoming request.

        Returns:
            Response: the answer to send back.
        """
        path = normalize_path(request.scope["path"])
        if is_blocked(path):
            logger.warning("Blocked %s %s", request.method, request.url.path)
            return Response(status_code=404)
        body = await request.body()
        if len(body) > self._config.max_body_bytes:
            return Response(status_code=413)
        try:
            upstream = await self._client.request(
                request.method,
                self._upstream_url(path, request.url.query),
                headers=self._forwarded_headers(request),
                content=body,
            )
        except httpx.TimeoutException:
            logger.error("Keycloak timed out on %s %s", request.method, path)
            return Response(status_code=504)
        except httpx.TransportError as error:
            logger.error("Keycloak is unreachable: %s", error)
            return Response(status_code=502)
        return _relayed(upstream)

    def _upstream_url(self, path: str, query: str) -> str:
        """Builds Keycloak's URL for a normalized path and the original query string.

        Args:
            path: The normalized path.
            query: The raw query string, without `?`.

        Returns:
            str: the absolute URL on the local Keycloak.
        """
        url = f"{self._config.upstream_origin}{quote(path, safe='/')}"
        return f"{url}?{query}" if query else url

    def _forwarded_headers(self, request: Request) -> list[tuple[str, str]]:
        """Copies the client's headers, minus hop and spoofable ones, plus the X-Forwarded set.

        Asks Keycloak for an uncompressed answer: without it httpx sends its own
        `Accept-Encoding`, and Keycloak gzips its static resources.

        Args:
            request: The incoming request.

        Returns:
            list[tuple[str, str]]: the headers to send to Keycloak, repeated names preserved.
        """
        headers = [
            (name, value)
            for name, value in request.headers.items()
            if name.lower() not in _DROPPED_REQUEST_HEADERS
        ]
        client_ip = request.client.host if request.client else ""
        return [
            *headers,
            ("Accept-Encoding", "identity"),
            ("X-Forwarded-Proto", "https"),
            ("X-Forwarded-Host", self._config.public_host),
            ("X-Forwarded-Port", "443"),
            ("X-Forwarded-For", client_ip),
        ]


def _relayed(upstream: httpx.Response) -> Response:
    """Turns Keycloak's answer into the gateway's, adding the missing hardening headers.

    Args:
        upstream: Keycloak's response.

    Returns:
        Response: the same status and body, every header but the hop-by-hop ones and
        `Server` (each `Set-Cookie` kept), plus any security header Keycloak did not set.
    """
    raw_headers = [
        (name.encode("latin-1"), value.encode("latin-1"))
        for name, value in upstream.headers.multi_items()
        if name.lower() not in _DROPPED_RESPONSE_HEADERS
    ]
    present = {name.lower() for name, _ in upstream.headers.multi_items()}
    raw_headers += [
        (name.encode("latin-1"), value.encode("latin-1"))
        for name, value in STATIC_SECURITY_HEADERS.items()
        if name.lower() not in present
    ]
    response = Response(content=upstream.content, status_code=upstream.status_code)
    response.raw_headers = [*raw_headers, (b"content-length", str(len(upstream.content)).encode())]
    return response


def build_gateway(config: GatewayConfig, client: httpx.AsyncClient | None = None) -> Starlette:
    """Builds the gateway's ASGI app.

    Args:
        config: Where Keycloak listens, and the public host it is served as.
        client: The HTTP client to Keycloak; by default one with the configured timeout that
            does not follow redirects.

    Returns:
        Starlette: the app the `auth` function serves.
    """
    http_client = client or httpx.AsyncClient(
        timeout=config.timeout_seconds, follow_redirects=False
    )
    gateway = KeycloakGateway(config, http_client)
    route = Route("/{path:path}", gateway.handle, methods=_ALL_METHODS)
    return Starlette(routes=[route])
