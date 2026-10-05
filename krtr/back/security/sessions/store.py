"""Stores krtr-web's server-side sessions in Neon's `app_sessions` table (task 4.4, D1).

Exists as the only code that reads or writes `app_sessions`: it runs the table's `.sql` files
and encrypts the OIDC tokens with AES-256-GCM (KRTR_TOKENS_KEY) before they reach the database,
so a database leak exposes neither cookies (only their hashes are stored) nor tokens. Consumed
by `krtr/back/security/sessions/service.py`.
"""

import logging
from datetime import datetime
from typing import Any

from krtr.back.security.crypto.cipher import AesGcmCipher
from krtr.back.security.oidc.artifacts import OidcTokens
from krtr.back.security.sessions.artifacts import SessionRecord
from krtr.database.neon.client import NeonClient
from krtr.database.queries import load_sql

logger = logging.getLogger(__name__)

TABLE = "app_sessions"
_INSERT_ONE = load_sql(TABLE, "insert_one.sql")
_SELECT_BY_HASH = load_sql(TABLE, "select_by_hash.sql")
_TOUCH_ACTIVITY = load_sql(TABLE, "touch_activity.sql")
_UPDATE_TOKENS = load_sql(TABLE, "update_tokens.sql")
_REVOKE_BY_ID = load_sql(TABLE, "revoke_by_id.sql")
_REVOKE_BY_CUSTOMER = load_sql(TABLE, "revoke_by_customer.sql")


class SessionStore:
    """Reads and writes `app_sessions` rows, encrypting the OIDC tokens they carry.

    Exists to keep SQL and encryption out of the session rules. Consumed by `SessionService`.
    """

    def __init__(self, client: NeonClient, cipher: AesGcmCipher) -> None:
        """Builds a store on one pooled Neon client and the tokens key.

        Args:
            client: The pooled Neon client (`execute_params` / `fetch_one`).
            cipher: The AES-256-GCM cipher for KRTR_TOKENS_KEY.
        """
        self._client = client
        self._cipher = cipher

    def insert(self, record: SessionRecord) -> None:
        """Stores a new session.

        Args:
            record: The session; its tokens are encrypted before being written.

        Returns:
            None.
        """
        self._client.execute_params(
            _INSERT_ONE,
            {
                "session_id_hash": record.session_id_hash,
                "customer_id": record.customer_id,
                "tokens_ciphertext": self._encrypt(record.tokens),
                "created_at": record.created_at,
                "last_activity_at": record.last_activity_at,
                "absolute_expires_at": record.absolute_expires_at,
            },
        )

    def find(self, session_id_hash: str) -> SessionRecord | None:
        """Loads a session by the hash of its cookie, revoked or not.

        Args:
            session_id_hash: The SHA-256 hex digest of the session cookie.

        Returns:
            SessionRecord | None: the session with its tokens decrypted, or None.
        """
        row = self._client.fetch_one(_SELECT_BY_HASH, {"session_id_hash": session_id_hash})
        return None if row is None else self._record_from(row)

    def touch(self, session_id_hash: str, at: datetime) -> None:
        """Records activity on a live session, pushing its idle deadline back.

        Args:
            session_id_hash: The session's cookie hash.
            at: When the activity happened.

        Returns:
            None.
        """
        self._client.execute_params(
            _TOUCH_ACTIVITY, {"session_id_hash": session_id_hash, "last_activity_at": at}
        )

    def replace_tokens(self, session_id_hash: str, tokens: OidcTokens) -> None:
        """Stores refreshed tokens for a live session.

        Args:
            session_id_hash: The session's cookie hash.
            tokens: The new tokens, encrypted before being written.

        Returns:
            None.
        """
        self._client.execute_params(
            _UPDATE_TOKENS,
            {"session_id_hash": session_id_hash, "tokens_ciphertext": self._encrypt(tokens)},
        )

    def revoke(self, session_id_hash: str, at: datetime) -> None:
        """Revokes one session (logout or expiry).

        Args:
            session_id_hash: The session's cookie hash.
            at: When it was revoked.

        Returns:
            None.
        """
        self._client.execute_params(
            _REVOKE_BY_ID, {"session_id_hash": session_id_hash, "revoked_at": at}
        )

    def revoke_customer(self, customer_id: str, at: datetime) -> int:
        """Revokes every live session of a customer, before a new login (1 session per user).

        Args:
            customer_id: The customer logging in again.
            at: When they were revoked.

        Returns:
            int: how many live sessions were revoked.
        """
        return self._client.execute_params(
            _REVOKE_BY_CUSTOMER, {"customer_id": customer_id, "revoked_at": at}
        )

    def _encrypt(self, tokens: OidcTokens) -> bytes:
        """Encrypts tokens for the `tokens_ciphertext` column.

        Args:
            tokens: The tokens to encrypt.

        Returns:
            bytes: nonce + ciphertext.
        """
        return self._cipher.encrypt(tokens.model_dump_json().encode("utf-8"))

    def _record_from(self, row: tuple[Any, ...]) -> SessionRecord:
        """Builds a SessionRecord from a `select_by_hash.sql` row, decrypting its tokens.

        Args:
            row: The row, in the query's column order.

        Returns:
            SessionRecord: the session.
        """
        (
            session_id_hash,
            customer_id,
            ciphertext,
            created_at,
            last_activity_at,
            absolute_expires_at,
            revoked_at,
        ) = row
        return SessionRecord(
            session_id_hash=session_id_hash,
            customer_id=customer_id,
            tokens=OidcTokens.model_validate_json(self._cipher.decrypt(bytes(ciphertext))),
            created_at=created_at,
            last_activity_at=last_activity_at,
            absolute_expires_at=absolute_expires_at,
            revoked_at=revoked_at,
        )
