"""Enforces krtr-web's session rules (task 4.4, G15).

Exists as the one place that decides whether a session cookie still opens a session: 5 minutes
without activity or 30 minutes since login end it, a new login ends the customer's previous
session, and the access token is refreshed shortly before it expires, which also keeps the
Keycloak session alive. The backend enforces this even if the frontend fails to. Consumed by
`krtr/back/web/routers/auth.py` and `krtr/back/web/routers/session.py`.
"""

import hashlib
import logging
import secrets
from datetime import datetime
from typing import Protocol

from krtr.back.security.clock import Clock, utc_now
from krtr.back.security.oidc.artifacts import OidcTokens
from krtr.back.security.oidc.errors import LoginError
from krtr.back.security.sessions.artifacts import (
    SessionEndReason,
    SessionRecord,
    SessionStatus,
    StartedSession,
)
from krtr.back.security.sessions.config import SESSION_TOKEN_BYTES, SessionConfig
from krtr.back.security.sessions.errors import SessionRejected
from krtr.back.security.sessions.store import SessionStore

logger = logging.getLogger(__name__)


class TokenRefresher(Protocol):
    """What the service needs to refresh a session's tokens; the OIDC client provides it.

    Exists so the session rules depend on a capability, not on Keycloak's HTTP API.
    """

    def refresh(self, refresh_token: str) -> OidcTokens:
        """Returns new tokens for a refresh token.

        Args:
            refresh_token: The session's current refresh token.

        Returns:
            OidcTokens: the new tokens.

        Raises:
            LoginError: if Keycloak refuses the refresh.
        """


def hash_session_token(token: str) -> str:
    """Returns the SHA-256 hex digest stored in place of a session cookie.

    Exists so the raw cookie never reaches the database: a leaked table cannot be replayed.

    Args:
        token: The session cookie's value.

    Returns:
        str: its 64-character hex digest.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class SessionService:
    """Starts, checks, extends and ends server-side sessions.

    Exists so every route applies the same G15 rules. Consumed by the auth and session routers.
    """

    def __init__(
        self,
        store: SessionStore,
        refresher: TokenRefresher,
        config: SessionConfig | None = None,
        clock: Clock = utc_now,
    ) -> None:
        """Builds the service.

        Args:
            store: Where sessions live (`app_sessions`).
            refresher: Refreshes OIDC tokens (the Keycloak client).
            config: The time limits; the G15 defaults when None.
            clock: Where the current time comes from (a fake clock in tests).
        """
        self._store = store
        self._refresher = refresher
        self._config = config or SessionConfig()
        self._clock = clock

    def start(self, customer_id: str, tokens: OidcTokens) -> StartedSession:
        """Opens a session after a login, ending the customer's previous ones.

        Args:
            customer_id: Who logged in.
            tokens: The tokens Keycloak issued for this login.

        Returns:
            StartedSession: the new cookie value (a fresh 256-bit token, so the session id is
            rotated on every login), the session's status, and how many sessions it replaced.
        """
        now = self._clock()
        replaced_sessions = self._store.revoke_customer(customer_id, now)
        token = secrets.token_urlsafe(SESSION_TOKEN_BYTES)
        record = SessionRecord(
            session_id_hash=hash_session_token(token),
            customer_id=customer_id,
            tokens=tokens,
            created_at=now,
            last_activity_at=now,
            absolute_expires_at=now + self._config.absolute_timeout,
        )
        self._store.insert(record)
        logger.info(
            "Started a session for customer %s (replaced %d)", customer_id, replaced_sessions
        )
        return StartedSession(
            token=token, status=self.status(record), replaced_sessions=replaced_sessions
        )

    def authenticate(self, token: str | None) -> SessionRecord:
        """Returns the live session a cookie opens, ending it first if it just expired.

        Args:
            token: The session cookie's value, or None when the request has none.

        Returns:
            SessionRecord: the live session.

        Raises:
            SessionRejected: if there is no such session, it was revoked, or it expired.
        """
        record = self._store.find(hash_session_token(token)) if token else None
        if record is None:
            raise SessionRejected(SessionEndReason.UNKNOWN)
        if record.revoked_at is not None:
            raise SessionRejected(SessionEndReason.REVOKED, record.customer_id)
        now = self._clock()
        expiry = self._expiry_reason(record, now)
        if expiry is not None:
            self._store.revoke(record.session_id_hash, now)
            raise SessionRejected(expiry, record.customer_id)
        return record

    def record_activity(self, record: SessionRecord) -> SessionStatus:
        """Pushes the idle deadline back, and refreshes the tokens if they are about to expire.

        Activity never moves the absolute deadline: a session still ends 30 minutes after login.

        Args:
            record: The live session (from `authenticate`).

        Returns:
            SessionStatus: the session's new deadlines.

        Raises:
            SessionRejected: if Keycloak refused to refresh the tokens; the session is revoked.
        """
        now = self._clock()
        self._store.touch(record.session_id_hash, now)
        active_record = record.model_copy(update={"last_activity_at": now})
        self._refresh_if_due(active_record, now)
        return self.status(active_record)

    def status(self, record: SessionRecord) -> SessionStatus:
        """Reports a session's deadlines; the idle one never passes the absolute one.

        Args:
            record: The session.

        Returns:
            SessionStatus: the customer and both deadlines.
        """
        idle_expires_at = min(
            record.last_activity_at + self._config.idle_timeout, record.absolute_expires_at
        )
        return SessionStatus(
            customer_id=record.customer_id,
            idle_expires_at=idle_expires_at,
            absolute_expires_at=record.absolute_expires_at,
        )

    def end(self, record: SessionRecord) -> None:
        """Revokes a session (logout).

        Args:
            record: The session to end.

        Returns:
            None.
        """
        self._store.revoke(record.session_id_hash, self._clock())

    def _expiry_reason(self, record: SessionRecord, now: datetime) -> SessionEndReason | None:
        """Tells whether a session reached one of its deadlines.

        Args:
            record: The session.
            now: The current time.

        Returns:
            SessionEndReason | None: ABSOLUTE or IDLE when expired, None while it is live.
        """
        if now >= record.absolute_expires_at:
            return SessionEndReason.ABSOLUTE
        if now >= record.last_activity_at + self._config.idle_timeout:
            return SessionEndReason.IDLE
        return None

    def _refresh_if_due(self, record: SessionRecord, now: datetime) -> None:
        """Refreshes the session's tokens when less than the margin is left.

        Args:
            record: The live session.
            now: The current time.

        Returns:
            None.

        Raises:
            SessionRejected: if Keycloak refuses; the session is revoked first.
        """
        if record.tokens.access_expires_at - now > self._config.token_refresh_margin:
            return
        try:
            tokens = self._refresher.refresh(record.tokens.refresh_token)
        except LoginError as error:
            logger.warning(
                "Keycloak refused to refresh the tokens of customer %s", record.customer_id
            )
            self._store.revoke(record.session_id_hash, now)
            raise SessionRejected(SessionEndReason.REVOKED, record.customer_id) from error
        self._store.replace_tokens(record.session_id_hash, tokens)
