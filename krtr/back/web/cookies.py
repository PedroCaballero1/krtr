"""Sets and clears krtr-web's three cookies (tasks 4.3, 4.4 and 4.5, D22).

Exists so the cookies' security flags are written once: all are `__Host-` (Secure, Path=/,
no Domain, so no other *.modal.run app can set or shadow them). The session cookie is
SameSite=Strict; the temporary login cookie is SameSite=Lax, because the return from Keycloak is
a top-level navigation that Strict would strip it from. Both are HttpOnly. The CSRF cookie is
SameSite=Strict but **not** HttpOnly: the SPA reads it and echoes it in `X-KRTR-CSRF` (double
submit); it is a random value, not a credential. Consumed by the auth router and
`krtr/back/web/dependencies.py`.
"""

from enum import StrEnum

from fastapi import Response

from krtr.back.security.csrf.config import CSRF_COOKIE_NAME
from krtr.back.security.oidc.config import LOGIN_COOKIE_LIFETIME, LOGIN_COOKIE_NAME
from krtr.back.security.sessions.config import SESSION_COOKIE_NAME, SessionConfig

COOKIE_PATH = "/"  # Required by the `__Host-` prefix.


class SameSitePolicy(StrEnum):
    """The SameSite values krtr-web's cookies use (D22)."""

    STRICT = "strict"
    LAX = "lax"


def set_login_cookie(response: Response, value: str) -> None:
    """Sets the encrypted login cookie for 10 minutes.

    Args:
        response: The redirect to Keycloak.
        value: The encoded LoginState.

    Returns:
        None.
    """
    _set(
        response,
        LOGIN_COOKIE_NAME,
        value,
        int(LOGIN_COOKIE_LIFETIME.total_seconds()),
        SameSitePolicy.LAX,
    )


def clear_login_cookie(response: Response) -> None:
    """Deletes the login cookie once the callback used it (or rejected it).

    Args:
        response: The callback's response.

    Returns:
        None.
    """
    _clear(response, LOGIN_COOKIE_NAME, SameSitePolicy.LAX)


def set_session_cookie(response: Response, token: str) -> None:
    """Sets the session cookie, expiring with the session's absolute limit.

    Args:
        response: The callback's redirect to /app.
        token: The session token.

    Returns:
        None.
    """
    _set(response, SESSION_COOKIE_NAME, token, _session_max_age(), SameSitePolicy.STRICT)


def clear_session_cookie(response: Response) -> None:
    """Deletes the session cookie (logout, or a rejected session).

    Args:
        response: The response that ends the session.

    Returns:
        None.
    """
    _clear(response, SESSION_COOKIE_NAME, SameSitePolicy.STRICT)


def set_csrf_cookie(response: Response, token: str) -> None:
    """Sets the CSRF cookie the SPA echoes back, for as long as the session can live.

    Args:
        response: The callback's redirect to /app.
        token: A fresh CSRF token.

    Returns:
        None.
    """
    _set(
        response,
        CSRF_COOKIE_NAME,
        token,
        _session_max_age(),
        SameSitePolicy.STRICT,
        http_only=False,
    )


def clear_csrf_cookie(response: Response) -> None:
    """Deletes the CSRF cookie, together with the session it protects.

    Args:
        response: The response that ends the session.

    Returns:
        None.
    """
    _clear(response, CSRF_COOKIE_NAME, SameSitePolicy.STRICT, http_only=False)


def _session_max_age() -> int:
    """Returns the session's absolute lifetime in seconds, the cookies' Max-Age.

    Returns:
        int: seconds until the session ends however active it is.
    """
    return int(SessionConfig().absolute_timeout.total_seconds())


def _set(
    response: Response,
    name: str,
    value: str,
    max_age: int,
    same_site: SameSitePolicy,
    http_only: bool = True,
) -> None:
    """Sets one `__Host-` cookie with krtr-web's flags.

    Args:
        response: Where to set it.
        name: The cookie's name.
        value: Its value.
        max_age: Its lifetime in seconds.
        same_site: Its SameSite policy.
        http_only: Whether scripts are kept from reading it; only the CSRF cookie is readable.

    Returns:
        None.
    """
    response.set_cookie(
        name,
        value,
        max_age=max_age,
        path=COOKIE_PATH,
        secure=True,
        httponly=http_only,
        samesite=same_site.value,
    )


def _clear(
    response: Response, name: str, same_site: SameSitePolicy, http_only: bool = True
) -> None:
    """Deletes one `__Host-` cookie; browsers ignore the deletion without the same flags.

    Args:
        response: Where to delete it.
        name: The cookie's name.
        same_site: The policy it was set with.
        http_only: The HttpOnly flag it was set with.

    Returns:
        None.
    """
    response.delete_cookie(
        name, path=COOKIE_PATH, secure=True, httponly=http_only, samesite=same_site.value
    )
