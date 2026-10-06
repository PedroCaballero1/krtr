"""Tests the Keycloak event sync (D3): complete, encrypted, idempotent and resumable."""

import json
import os
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from krtr.back.security.audit import config as config_module
from krtr.back.security.audit import keycloak_sync
from krtr.back.security.audit.config import AuditEnvironmentVariable
from krtr.back.security.audit.keycloak_sync import (
    KEYCLOAK_EVENT_NAME_PREFIX,
    sync_auth_events,
    sync_auth_events_from_environment,
)
from krtr.back.security.crypto.cipher import AesGcmCipher
from krtr.database.queries import load_sql
from tests.back.security.audit.fakes import refuse_to_open_neon

OVERLAP = timedelta(minutes=15)
TEN_O_CLOCK = datetime(2026, 10, 5, 10, 0, tzinfo=UTC)


def keycloak_event(
    event_id: str, event_type: str, at: datetime, details: dict[str, Any] | None = None
) -> tuple[Any, ...]:
    """Builds an `event_entity` row in the column order of `event_entity/query.sql`."""
    return (
        event_id,
        event_type,
        int(at.timestamp() * 1000),
        "realm-krtr",
        "krtr-web",
        "user-1",
        "session-1",
        "203.0.113.7",
        "invalid_user_credentials" if event_type.endswith("_ERROR") else None,
        json.dumps(details or {"username": "cli-000000000001"}),
    )


class FakeKeycloakDatabase:
    """Stands in for the `keycloak` database: serves the events from the requested time on."""

    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        """Holds Keycloak's `event_entity` rows."""
        self.rows = rows
        self.reads: list[dict[str, Any]] = []

    def fetch_all(self, statement: str, params: dict[str, Any]) -> list[tuple[Any, ...]]:
        """Applies the `event_time >= since` filter of `event_entity/query.sql`."""
        self.reads.append(params)
        return [row for row in self.rows if row[2] >= params["since_epoch_ms"]]


class FakeEventsDatabase:
    """Stands in for the app database, with the semantics of the two `events` queries."""

    def __init__(self, rows: list[tuple[Any, ...]] | None = None) -> None:
        """Holds `events` rows by id."""
        self.rows = {row[0]: row for row in rows or []}

    def fetch_one(self, statement: str, params: dict[str, Any]) -> tuple[Any, ...]:
        """Returns the latest time among the events with the prefix, like the watermark query."""
        prefix = params["event_name_prefix"]
        times = [row[3] for row in self.rows.values() if row[1].startswith(prefix)]
        return (max(times) if times else None,)

    def insert_rows(self, statement: str, rows: list[tuple[Any, ...]]) -> int:
        """Inserts the rows whose id is new, like `ON CONFLICT (id) DO NOTHING`."""
        new_rows = [row for row in rows if row[0] not in self.rows]
        self.rows.update({row[0]: row for row in new_rows})
        return len(new_rows)


@pytest.fixture
def cipher() -> AesGcmCipher:
    """A cipher with a throwaway key."""
    return AesGcmCipher(os.urandom(32))


def decrypted_properties(row: tuple[Any, ...], cipher: AesGcmCipher) -> dict[str, Any]:
    """Decrypts an `events` row's properties."""
    return json.loads(cipher.decrypt(row[2]))


def test_the_first_run_copies_every_keycloak_event_encrypted(cipher: AesGcmCipher) -> None:
    """Each event keeps Keycloak's id and time, is named auth_keycloak_*, and is unreadable."""
    keycloak = FakeKeycloakDatabase(
        [
            keycloak_event("id-login", "LOGIN", TEN_O_CLOCK),
            keycloak_event("id-error", "LOGIN_ERROR", TEN_O_CLOCK + timedelta(seconds=1)),
        ]
    )
    events = FakeEventsDatabase()

    result = sync_auth_events(keycloak, events, cipher, OVERLAP)

    assert (result.since, result.read, result.inserted) == (None, 2, 2)
    assert keycloak.reads == [{"since_epoch_ms": 0}]
    login, error = events.rows["id-login"], events.rows["id-error"]
    assert (login[1], login[3]) == ("auth_keycloak_login", TEN_O_CLOCK)
    assert error[1] == "auth_keycloak_login_error"
    assert b"cli-000000000001" not in error[2]
    properties = decrypted_properties(error, cipher)
    assert properties["error"] == "invalid_user_credentials"
    assert properties["details"] == {"username": "cli-000000000001"}
    assert (properties["user_id"], properties["ip_address"]) == ("user-1", "203.0.113.7")


def test_running_again_adds_nothing(cipher: AesGcmCipher) -> None:
    """A retry or an overlapping run must not duplicate events."""
    keycloak = FakeKeycloakDatabase([keycloak_event("id-login", "LOGIN", TEN_O_CLOCK)])
    events = FakeEventsDatabase()
    sync_auth_events(keycloak, events, cipher, OVERLAP)

    result = sync_auth_events(keycloak, events, cipher, OVERLAP)

    assert (result.read, result.inserted) == (1, 0)
    assert list(events.rows) == ["id-login"]


def test_the_insert_skips_ids_already_in_events() -> None:
    """The idempotency the fake above assumes is the SQL's, not the Python's."""
    statement = load_sql("events", "insert_new.sql")

    assert "ON CONFLICT (id) DO NOTHING" in statement


def test_it_resumes_before_the_latest_copy_and_catches_late_events(
    cipher: AesGcmCipher,
) -> None:
    """An event Keycloak commits after a run, with an earlier time, is still copied next time."""
    keycloak = FakeKeycloakDatabase([keycloak_event("id-a", "LOGIN", TEN_O_CLOCK)])
    events = FakeEventsDatabase()
    sync_auth_events(keycloak, events, cipher, OVERLAP)
    keycloak.rows += [
        keycloak_event("id-late", "LOGOUT", TEN_O_CLOCK - timedelta(minutes=5)),
        keycloak_event("id-next", "LOGIN", TEN_O_CLOCK + timedelta(minutes=10)),
    ]

    result = sync_auth_events(keycloak, events, cipher, OVERLAP)

    assert result.since == TEN_O_CLOCK - OVERLAP
    assert keycloak.reads[-1] == {"since_epoch_ms": int((TEN_O_CLOCK - OVERLAP).timestamp() * 1000)}
    assert (result.read, result.inserted) == (3, 2)
    assert set(events.rows) == {"id-a", "id-late", "id-next"}


def test_the_apps_own_auth_events_do_not_move_the_mark(cipher: AesGcmCipher) -> None:
    """The app's later auth_logout must not make the sync skip Keycloak events before it."""
    app_logout = ("app-1", "auth_logout", b"", TEN_O_CLOCK + timedelta(hours=2))
    copied = ("id-a", f"{KEYCLOAK_EVENT_NAME_PREFIX}login", b"", TEN_O_CLOCK)
    events = FakeEventsDatabase([app_logout, copied])

    result = sync_auth_events(FakeKeycloakDatabase([]), events, cipher, OVERLAP)

    assert result.since == TEN_O_CLOCK - OVERLAP


def test_credential_like_details_never_reach_the_audit_log(cipher: AesGcmCipher) -> None:
    """Same last line of defense as EventRecorder, applied to what Keycloak sends."""
    details = {"username": "cli-1", "password": "secret", "Token": "abc", "code_id": "c-1"}
    keycloak = FakeKeycloakDatabase([keycloak_event("id-1", "LOGIN", TEN_O_CLOCK, details)])
    events = FakeEventsDatabase()

    sync_auth_events(keycloak, events, cipher, OVERLAP)

    properties = decrypted_properties(events.rows["id-1"], cipher)
    assert properties["details"] == {"username": "cli-1", "code_id": "c-1"}


def test_a_missing_connection_fails_before_opening_any(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without the audit URL the sync stops naming it, and no connection is left behind."""
    monkeypatch.setattr(config_module, "load_dotenv", lambda: None)
    monkeypatch.delenv(AuditEnvironmentVariable.KEYCLOAK_EVENTS_URL, raising=False)
    monkeypatch.setattr(keycloak_sync, "NeonClient", lambda *_args: refuse_to_open_neon())

    with pytest.raises(ValueError, match="KRTR_AUDIT_DB_URL"):
        sync_auth_events_from_environment()
