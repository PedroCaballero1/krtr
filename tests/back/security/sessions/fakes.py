"""Fakes shared by the session and router tests: an in-memory store and a token refresher."""

from datetime import datetime, timedelta

from krtr.back.security.oidc.artifacts import OidcTokens
from krtr.back.security.oidc.errors import LoginError, LoginFailureReason
from krtr.back.security.sessions.artifacts import SessionRecord
from tests.back.security.oidc.fakes import FakeClock


def tokens_expiring_at(expires_at: datetime, generation: int = 0) -> OidcTokens:
    """Builds tokens whose access token expires at the given time."""
    return OidcTokens(
        access_token=f"access-{generation}",
        refresh_token=f"refresh-{generation}",
        id_token=f"id-{generation}",
        access_expires_at=expires_at,
    )


class InMemorySessionStore:
    """Stands in for SessionStore, keeping sessions in a dict keyed by cookie hash."""

    def __init__(self) -> None:
        """Starts empty."""
        self.sessions: dict[str, SessionRecord] = {}

    def insert(self, record: SessionRecord) -> None:
        """Stores a session."""
        self.sessions[record.session_id_hash] = record

    def find(self, session_id_hash: str) -> SessionRecord | None:
        """Returns a session by hash, or None."""
        return self.sessions.get(session_id_hash)

    def touch(self, session_id_hash: str, at: datetime) -> None:
        """Updates a live session's last activity."""
        self._update_live(session_id_hash, last_activity_at=at)

    def replace_tokens(self, session_id_hash: str, tokens: OidcTokens) -> None:
        """Replaces a live session's tokens."""
        self._update_live(session_id_hash, tokens=tokens)

    def revoke(self, session_id_hash: str, at: datetime) -> None:
        """Revokes one live session."""
        self._update_live(session_id_hash, revoked_at=at)

    def revoke_customer(self, customer_id: str, at: datetime) -> int:
        """Revokes a customer's live sessions and returns how many."""
        live = [
            h
            for h, r in self.sessions.items()
            if r.customer_id == customer_id and r.revoked_at is None
        ]
        for session_id_hash in live:
            self.revoke(session_id_hash, at)
        return len(live)

    def _update_live(self, session_id_hash: str, **changes: object) -> None:
        """Applies changes to a session only while it is not revoked, like the SQL does."""
        record = self.sessions.get(session_id_hash)
        if record is not None and record.revoked_at is None:
            self.sessions[session_id_hash] = record.model_copy(update=changes)


class FakeRefresher:
    """Stands in for the OIDC client's refresh, issuing 5-minute tokens or refusing."""

    def __init__(self, clock: FakeClock) -> None:
        """Refreshes successfully until told to refuse."""
        self.clock = clock
        self.calls: list[str] = []
        self.refuse = False

    def refresh(self, refresh_token: str) -> OidcTokens:
        """Returns new tokens, or raises like Keycloak when its session ended."""
        self.calls.append(refresh_token)
        if self.refuse:
            raise LoginError(LoginFailureReason.TOKEN_EXCHANGE_FAILED)
        return tokens_expiring_at(self.clock() + timedelta(minutes=5), generation=len(self.calls))
