"""Defines the data the OIDC login produces and carries (task 4.3).

Exists to keep the login's contracts — what the temporary cookie holds, what Keycloak returns,
and who logged in — discoverable apart from the flow that uses them. Consumed by
`krtr/back/security/oidc/` and `krtr/back/security/sessions/`.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class InterfaceLanguage(StrEnum):
    """The languages of the krtr interface and login (G14), as `ui_locales` values.

    Exists so `/auth/login?lang=` only accepts the two languages realm-krtr.json supports.
    Consumed by `krtr/back/web/routers/auth.py` and the OIDC client.
    """

    SPANISH = "es"  # The default (D14).
    PORTUGUESE = "pt-BR"


class LoginState(BaseModel):
    """What the encrypted `__Host-krtr_oidc` cookie carries from /auth/login to /auth/callback.

    Exists so the callback can check that it answers the login this browser started (`state`),
    that the ID token was issued for it (`nonce`), and can prove PKCE (`code_verifier`).
    """

    state: str
    nonce: str
    code_verifier: str
    language: InterfaceLanguage
    expires_at: datetime


class OidcTokens(BaseModel):
    """The tokens Keycloak issues for a session; stored only encrypted (`app_sessions`).

    Exists so sessions can refresh the access token before it expires and end the Keycloak
    session on logout. Never logged and never sent to the browser.
    """

    access_token: str
    refresh_token: str
    id_token: str
    access_expires_at: datetime


class LoginIdentity(BaseModel):
    """Who logged in, from a validated ID token.

    Exists so the session layer receives the customer, never raw token claims.
    """

    customer_id: str  # The Keycloak username, which is the dataset's customer_id (G6).
    subject: str  # Keycloak's stable user id (`sub`).
