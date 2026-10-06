"""Tests the `messages` SQL contract: encrypted text, the index, scoped reads, retention."""

from krtr.database.queries import load_sql

TABLE_SQL = load_sql("messages", "table.sql")


def test_content_is_stored_as_ciphertext_bytes() -> None:
    """The text column holds AES-GCM output, never readable text."""
    assert "content BYTEA NOT NULL" in TABLE_SQL


def test_the_explicitly_requested_index_covers_the_case_lookup() -> None:
    """The one index serves exactly the filter every read uses."""
    assert "ON messages (incident_id, customer_id);" in TABLE_SQL


def test_reads_always_filter_by_incident_and_customer() -> None:
    """A query by incident alone would let one customer read another's case."""
    select_sql = load_sql("messages", "select_by_case.sql")

    assert "WHERE incident_id = %(incident_id)s" in select_sql
    assert "AND customer_id = %(customer_id)s" in select_sql


def test_retention_is_three_months() -> None:
    """Same retention as `events` (decided 2026-10-05)."""
    assert "sent_at < now() - interval '3 months'" in load_sql("messages", "purge.sql")
