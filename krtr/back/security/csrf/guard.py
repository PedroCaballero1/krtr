"""Checks state-changing requests against cross-site request forgery (task 4.5).

Exists because `SameSite` alone does not protect krtr-web: `modal.run` is shared by every Modal
app, so a page on another `*.modal.run` app can be "same-site". Two independent checks apply:

- **Origin:** the request's `Origin` (or, without it, its `Referer`) must be krtr-web's own
  origin. A request naming no origin at all is rejected.
- **Double submit:** the `X-KRTR-CSRF` header must echo the `__Host-krtr_csrf` cookie. Another
  origin can neither read that cookie nor, thanks to `__Host-`, set it.

Framework-free, so it is tested without HTTP. Consumed by `krtr/back/web/csrf.py`.
"""

import secrets

from krtr.back.security.csrf.config import origin_of
from krtr.back.security.csrf.errors import CsrfFailureReason, CsrfRejected

CSRF_TOKEN_BYTES = 32  # 256 bits, like the session token.


def new_csrf_token() -> str:
    """Generates a fresh CSRF token for a new session.

    Returns:
        str: a URL-safe random token, safe to put in a cookie unencoded.
    """
    return secrets.token_urlsafe(CSRF_TOKEN_BYTES)


def check_origin(origin: str | None, referer: str | None, allowed_origin: str) -> None:
    """Accepts a request only if it says it comes from krtr-web's own origin.

    `Origin` decides when present; `Referer` is the fallback for clients that omit it.

    Args:
        origin: The request's `Origin` header.
        referer: The request's `Referer` header.
        allowed_origin: krtr-web's origin, from `CsrfConfig.allowed_origin`.

    Returns:
        None.

    Raises:
        CsrfRejected: MISSING_ORIGIN or FOREIGN_ORIGIN.
    """
    claimed = origin_of(origin) or origin_of(referer)
    if claimed is None:
        raise CsrfRejected(CsrfFailureReason.MISSING_ORIGIN)
    if claimed != allowed_origin:
        raise CsrfRejected(CsrfFailureReason.FOREIGN_ORIGIN)


def check_token(cookie_token: str | None, header_token: str | None) -> None:
    """Accepts a request only if its header echoes its CSRF cookie, compared in constant time.

    Args:
        cookie_token: The `__Host-krtr_csrf` cookie.
        header_token: The `X-KRTR-CSRF` header.

    Returns:
        None.

    Raises:
        CsrfRejected: MISSING_TOKEN or TOKEN_MISMATCH.
    """
    if not cookie_token or not header_token:
        raise CsrfRejected(CsrfFailureReason.MISSING_TOKEN)
    if not secrets.compare_digest(cookie_token.encode(), header_token.encode()):
        raise CsrfRejected(CsrfFailureReason.TOKEN_MISMATCH)
