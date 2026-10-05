"""Sets and clears krtr-web's two cookies (tasks 4.3 and 4.4, D22).

Exists so the cookies' security flags are written once: both are `__Host-` (Secure, Path=/,
no Domain, so no other *.modal.run app can set or shadow them) and HttpOnly. The session cookie
is SameSite=Strict; the temporary login cookie is SameSite=Lax, because the return from
Keycloak is a top-level navigation that Strict would strip it from. Consumed by the auth router
and `krtr/back/web/dependencies.py`.
"""

from enum import StrEnum

from fastapi import Response

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
    max_age = int(SessionConfig().absolute_timeout.total_seconds())
    _set(response, SESSION_COOKIE_NAME, token, max_age, SameSitePolicy.STRICT)


def clear_session_cookie(response: Response) -> None:
    """Deletes the session cookie (logout, or a rejected session).

    Args:
        response: The response that ends the session.

    Returns:
        None.
    """
    _clear(response, SESSION_COOKIE_NAME, SameSitePolicy.STRICT)


def _set(
    response: Response, name: str, value: str, max_age: int, same_site: SameSitePolicy
) -> None:
    """Sets one `__Host-` cookie with krtr-web's flags.

    Args:
        response: Where to set it.
        name: The cookie's name.
        value: Its value.
        max_age: Its lifetime in seconds.
        same_site: Its SameSite policy.

    Returns:
        None.
    """
    response.set_cookie(
        name,
        value,
        max_age=max_age,
        path=COOKIE_PATH,
        secure=True,
        httponly=True,
        samesite=same_site.value,
    )


def _clear(response: Response, name: str, same_site: SameSitePolicy) -> None:
    """Deletes one `__Host-` cookie; browsers ignore the deletion without the same flags.

    Args:
        response: Where to delete it.
        name: The cookie's name.
        same_site: The policy it was set with.

    Returns:
        None.
    """
    response.delete_cookie(
        name, path=COOKIE_PATH, secure=True, httponly=True, samesite=same_site.value
    )
