"""Tests the events purge: it runs the retention SQL and reports what it deleted."""

from typing import Any

from krtr.back.security.audit.retention import purge_expired_events


class FakeNeonClient:
    """Stands in for NeonClient: records the statement and reports a row count."""

    def __init__(self, deleted: int) -> None:
        """Reports `deleted` rows for any statement."""
        self.deleted = deleted
        self.statements: list[str] = []

    def execute_params(self, statement: str, params: dict[str, Any] | None = None) -> int:
        """Records the statement."""
        self.statements.append(statement)
        return self.deleted


def test_the_purge_deletes_only_what_is_past_three_months() -> None:
    """Recent events must survive; the SQL bounds the delete by the 3-month retention."""
    client = FakeNeonClient(deleted=7)

    deleted = purge_expired_events(client)

    assert deleted == 7
    assert "DELETE FROM events" in client.statements[0]
    assert "interval '3 months'" in client.statements[0]
