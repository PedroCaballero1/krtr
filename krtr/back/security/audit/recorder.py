"""Implements writing events to the encrypted `events` table (G21).

Exists as the single place that turns an `EventName` and a properties dict
into an encrypted row, so no caller ever writes to `events` directly or
handles the encryption itself. Consumed by
`krtr/back/security/audit/middleware.py` and `krtr/back/web/routers/events.py`.
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from krtr.back.security.audit.event_names import EventName
from krtr.back.security.crypto.cipher import AesGcmCipher
from krtr.database.neon.client import NeonClient
from krtr.database.queries import load_sql

logger = logging.getLogger(__name__)

_INSERT_ONE_STATEMENT = load_sql("events", "insert_one.sql")

# Never allowed in an event's properties, regardless of caller: a bug that
# adds one of these must not silently persist a credential.
FORBIDDEN_PROPERTY_KEYS = frozenset({"password", "token", "tokens", "cookie", "cookies"})


class EventRecorder:
    """Encrypts and writes events to the `events` table.

    Exists to centralize the write path for G21's single audit-log table:
    every event this backend records goes through one instance of this
    class instead of ad hoc inserts. Consumed by the audit middleware and
    the `POST /api/events` route.
    """

    def __init__(self, client: NeonClient, cipher: AesGcmCipher) -> None:
        """Builds a recorder bound to one pooled client and one cipher.

        Args:
            client: Pooled Neon client (see `NeonClient.execute_params`)
                used to write event rows without blocking on a dedicated
                connection per event.
            cipher: The AES-256-GCM cipher used to encrypt `properties`.
        """
        self._client = client
        self._cipher = cipher

    def record_event(self, event_name: EventName, properties: dict[str, Any]) -> None:
        """Encrypts `properties` and writes one event row.

        Exists so every event is written the same way: serialized to JSON,
        encrypted, and inserted with a fresh id and the current UTC time.

        Args:
            event_name: The event's type, from the `EventName` catalog.
            properties: The event's JSON-serializable properties. Must never
                include passwords, tokens or cookies (see
                `FORBIDDEN_PROPERTY_KEYS`).

        Returns:
            None.

        Raises:
            ValueError: if `properties` contains a forbidden key.
        """
        _assert_no_forbidden_keys(properties)
        payload = json.dumps(properties, sort_keys=True).encode("utf-8")
        ciphertext = self._cipher.encrypt(payload)
        self._client.execute_params(
            _INSERT_ONE_STATEMENT,
            {
                "id": str(uuid4()),
                "event_name": event_name.value,
                "properties": ciphertext,
                "occurred_at": datetime.now(UTC),
            },
        )
        logger.debug("Recorded event %s", event_name.value)


def _assert_no_forbidden_keys(properties: dict[str, Any]) -> None:
    """Raises if any of `properties`'s keys look like a credential.

    Exists as a last line of defense so a future caller's bug can't persist
    a secret to the audit log, even encrypted.

    Args:
        properties: The event properties about to be recorded.

    Returns:
        None.

    Raises:
        ValueError: if a key (case-insensitively) matches a forbidden name.
    """
    lowercase_keys = {key.lower() for key in properties}
    forbidden_found = lowercase_keys & FORBIDDEN_PROPERTY_KEYS
    if forbidden_found:
        raise ValueError(f"Event properties must never include: {sorted(forbidden_found)}")
