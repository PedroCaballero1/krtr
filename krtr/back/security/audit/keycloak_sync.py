"""Copies Keycloak's login events into the encrypted `events` table (task 4.10, D3).

Exists so G21's single audit table also holds what only Keycloak sees (logins, failed attempts,
lockouts, logouts, token exchanges). Keycloak writes them to `event_entity` in its own database;
this job reads them from the latest copied event on, as krtr_audit_reader, and inserts each one
as `auth_keycloak_<type>` with its properties encrypted like every other event. Each copy keeps
the Keycloak event's id, so re-reading an event never duplicates it. Consumed by the
`sync_auth_events` Modal cron (task 6.5) and `krtr back security audit sync-auth-events`.
"""

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from krtr.back.security.audit.artifacts import AuthEventSyncResult
from krtr.back.security.audit.config import AuthEventSyncConfig
from krtr.back.security.audit.recorder import FORBIDDEN_PROPERTY_KEYS
from krtr.back.security.crypto.cipher import AesGcmCipher
from krtr.back.security.crypto.config import CryptoConfig
from krtr.database.neon.client import NeonClient
from krtr.database.neon.config import NeonConfig
from krtr.database.queries import load_sql

logger = logging.getLogger(__name__)

# Keycloak's types (LOGIN, LOGIN_ERROR, LOGOUT, ...) go after it, in lower case. The prefix keeps
# them apart from the app's own auth_* events, such as its auth_logout.
KEYCLOAK_EVENT_NAME_PREFIX = "auth_keycloak_"

_SELECT_KEYCLOAK_EVENTS = load_sql("event_entity", "query.sql")
_SELECT_WATERMARK = load_sql("events", "keycloak_watermark.sql")
_INSERT_NEW_EVENTS = load_sql("events", "insert_new.sql")

_MILLISECONDS_PER_SECOND = 1000

KeycloakEventRow = tuple[Any, ...]  # The columns of event_entity/query.sql, in order.
EventRow = tuple[str, str, bytes, datetime]  # The columns of events/insert_new.sql, in order.


def sync_auth_events(
    keycloak: NeonClient, events: NeonClient, cipher: AesGcmCipher, overlap: timedelta
) -> AuthEventSyncResult:
    """Copies the Keycloak events not yet in `events`, encrypted, and reports what it did.

    Exists as the one sync step the cron and the CLI share. It re-reads `overlap` before the
    latest copied event, so an event Keycloak committed late is still picked up, and relies on
    the insert skipping known ids, so running it twice, or concurrently, never duplicates.

    Args:
        keycloak: Client of the `keycloak` database, as krtr_audit_reader.
        events: Client of the app database, which holds `events`.
        cipher: The AES-256-GCM cipher of `events.properties` (`KRTR_EVENTS_KEY`).
        overlap: How far before the latest copied event to read again.

    Returns:
        AuthEventSyncResult: where the run resumed from, and how many events it read and added.
    """
    since = _resume_point(events, overlap)
    keycloak_rows = keycloak.fetch_all(
        _SELECT_KEYCLOAK_EVENTS, {"since_epoch_ms": _epoch_milliseconds(since)}
    )
    event_rows = [_to_event_row(row, cipher) for row in keycloak_rows]
    inserted = events.insert_rows(_INSERT_NEW_EVENTS, event_rows)
    logger.info(
        "Synced Keycloak events since %s: %d read, %d new",
        since.isoformat() if since else "the beginning",
        len(keycloak_rows),
        inserted,
    )
    return AuthEventSyncResult(since=since, read=len(keycloak_rows), inserted=inserted)


def sync_auth_events_from_environment() -> AuthEventSyncResult:
    """Runs `sync_auth_events` with the connections and key the environment configures.

    Exists so the cron and the CLI wire it the same way. The key and the connection string are
    validated before any connection opens, so a bad configuration never leaves one behind.

    Args:
        None.

    Returns:
        AuthEventSyncResult: what the run did.

    Raises:
        ValueError: if `KRTR_AUDIT_DB_URL`, `NEON_DB_HOST` or `KRTR_EVENTS_KEY` is missing, or
            the key is not a base64-encoded 32-byte key.
    """
    config = AuthEventSyncConfig.from_environment()
    cipher = AesGcmCipher(CryptoConfig.from_environment().decoded_key())
    events_config = NeonConfig.from_environment()
    keycloak_config = NeonConfig(connection_string=config.keycloak_events_connection_string)
    with NeonClient(keycloak_config) as keycloak, NeonClient(events_config) as events:
        return sync_auth_events(keycloak, events, cipher, config.overlap)


def _resume_point(events: NeonClient, overlap: timedelta) -> datetime | None:
    """Returns the time to read Keycloak events from: the latest copied one minus the overlap.

    Args:
        events: Client of the app database.
        overlap: How far before the latest copied event to read again.

    Returns:
        datetime | None: the resume point, or None when nothing was copied yet.
    """
    row = events.fetch_one(_SELECT_WATERMARK, {"event_name_prefix": KEYCLOAK_EVENT_NAME_PREFIX})
    latest = row[0] if row else None
    return None if latest is None else latest - overlap


def _epoch_milliseconds(moment: datetime | None) -> int:
    """Converts a resume point to Keycloak's `event_time` unit.

    Args:
        moment: The resume point, or None to read from the beginning.

    Returns:
        int: epoch milliseconds; 0 for None.
    """
    return 0 if moment is None else int(moment.timestamp() * _MILLISECONDS_PER_SECOND)


def _to_event_row(row: KeycloakEventRow, cipher: AesGcmCipher) -> EventRow:
    """Turns one `event_entity` row into an `events` row with encrypted properties.

    Args:
        row: The columns of `event_entity/query.sql`, in order.
        cipher: The events cipher.

    Returns:
        EventRow: id (Keycloak's), event name, encrypted properties and time, in UTC.
    """
    (
        event_id,
        event_type,
        event_time,
        realm_id,
        client_id,
        user_id,
        session_id,
        ip_address,
        error,
        details_json,
    ) = row
    properties = {
        "keycloak_type": event_type,
        "realm_id": realm_id,
        "client_id": client_id,
        "user_id": user_id,
        "session_id": session_id,
        "ip_address": ip_address,
        "error": error,
        "details": _safe_details(details_json),
    }
    payload = json.dumps(properties, sort_keys=True).encode("utf-8")
    occurred_at = datetime.fromtimestamp(event_time / _MILLISECONDS_PER_SECOND, UTC)
    event_name = f"{KEYCLOAK_EVENT_NAME_PREFIX}{event_type.lower()}"
    return (event_id, event_name, cipher.encrypt(payload), occurred_at)


def _safe_details(details_json: str | None) -> dict[str, Any]:
    """Parses an event's details, dropping any key that looks like a credential.

    Exists as the same last line of defense `EventRecorder` applies: Keycloak does not put
    secrets in event details, but if a future version did, they must not reach the audit log.

    Args:
        details_json: The event's details as Keycloak stored them, or None.

    Returns:
        dict[str, Any]: the details without forbidden keys; empty when there are none.
    """
    details = json.loads(details_json) if details_json else {}
    return {
        key: value for key, value in details.items() if key.lower() not in FORBIDDEN_PROPERTY_KEYS
    }
