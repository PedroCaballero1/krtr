"""Defines the configuration of krtr-web's CSRF protection (task 4.5).

Exists so the one origin krtr-web accepts state-changing requests from is read from the
environment in one place. It is the app's public URL (KRTR_PUBLIC_URL), the same one the OIDC
callback is built from, so the login and the CSRF check can never disagree on where krtr-web
lives. Consumed by `krtr/back/security/csrf/guard.py` and `krtr/back/web/csrf.py`.
"""

import logging
import os
from urllib.parse import urlsplit

from pydantic import BaseModel

from krtr.back.security.oidc.config import DEFAULT_PUBLIC_URL, OidcEnvironmentVariable

logger = logging.getLogger(__name__)

# The double-submit cookie and header (task 4.5). The cookie is `__Host-` like the others, so
# no other *.modal.run app can set it, and it is readable by the SPA, which echoes it back.
CSRF_COOKIE_NAME = "__Host-krtr_csrf"
CSRF_HEADER_NAME = "X-KRTR-CSRF"

_DEFAULT_PORTS = {"http": 80, "https": 443}


def origin_of(url: str | None) -> str | None:
    """Reduces a URL to its origin, `scheme://host[:port]`, the way browsers write `Origin`.

    Exists so the configured public URL, an `Origin` header and a `Referer` header compare
    equal when they name the same origin, whatever their path, letter case or default port.

    Args:
        url: An absolute URL, or None.

    Returns:
        str | None: the lowercase origin with the default port dropped, or None if `url` is
        missing, relative, or the literal `null` browsers send for opaque origins.
    """
    if not url:
        return None
    parts = urlsplit(url.strip())
    if not parts.scheme or not parts.hostname:
        return None
    scheme = parts.scheme.lower()
    port = parts.port
    host = parts.hostname.lower()
    if port is None or port == _DEFAULT_PORTS.get(scheme):
        return f"{scheme}://{host}"
    return f"{scheme}://{host}:{port}"


class CsrfConfig(BaseModel):
    """Settings of the CSRF protection: the origin krtr-web is served from.

    Exists to give the guard a validated, typed settings object instead of reading the
    environment inline. Consumed by `krtr/back/web/app.py`.
    """

    public_url: str = DEFAULT_PUBLIC_URL

    @property
    def allowed_origin(self) -> str:
        """Returns the only origin state-changing requests may come from.

        Returns:
            str: the public URL's origin.

        Raises:
            ValueError: if the public URL is not an absolute URL.
        """
        origin = origin_of(self.public_url)
        if origin is None:
            raise ValueError(f"KRTR_PUBLIC_URL is not an absolute URL: {self.public_url!r}")
        return origin

    @classmethod
    def from_environment(cls) -> "CsrfConfig":
        """Builds a CsrfConfig from KRTR_PUBLIC_URL, defaulting to the local server.

        Args:
            None.

        Returns:
            CsrfConfig: the resolved configuration.
        """
        settings: dict[str, str] = {}
        if public_url := os.environ.get(OidcEnvironmentVariable.PUBLIC_URL):
            settings["public_url"] = public_url
        logger.debug("Loaded CSRF configuration from the environment: %s", settings)
        return cls(**settings)
