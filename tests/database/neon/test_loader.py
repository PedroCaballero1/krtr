"""Tests loading rows from Parquet into a table, batching and validating them."""

from pathlib import Path

import polars as pl
import pytest

from krtr.database.neon import loader
from krtr.database.neon.artifacts import ColumnSpec, LoadSummary
from krtr.database.neon.loader import DEFAULT_BATCH_SIZE, load_table, run_table_load
from krtr.database.neon.validation import RowValidationError

PRODUCTS_SPECS = [
    ColumnSpec(name="product_id", data_type="character varying", is_nullable=False),
    ColumnSpec(name="current_balance", data_type="numeric", is_nullable=False),
    ColumnSpec(name="opening_date", data_type="date", is_nullable=False),
]


class FakeClient:
    """Stands in for NeonClient, recording inserted batches instead of writing them."""

    def __init__(self, column_specs: list[ColumnSpec]) -> None:
        """Serves fixed column specs and starts with no recorded inserts."""
        self._column_specs = column_specs
        self.inserted_batches: list[list[tuple]] = []

    def get_column_specs(self, table_name: str) -> list[ColumnSpec]:
        """Returns the fixed column specs regardless of table name."""
        return self._column_specs

    def insert_rows(self, statement: str, rows: list[tuple]) -> None:
        """Records the batch instead of inserting it into a database."""
        self.inserted_batches.append(list(rows))


def make_parquet(tmp_path: Path, opening_dates: list[str]) -> Path:
    """Writes a small products.parquet with one row per given opening_date string."""
    path = tmp_path / "products.parquet"
    pl.DataFrame(
        {
            "product_id": [f"P{i}" for i in range(len(opening_dates))],
            "current_balance": [float(i) * 10 for i in range(len(opening_dates))],
            "opening_date": opening_dates,
        }
    ).write_parquet(path)
    return path


def test_load_table_inserts_all_valid_rows_in_batches(tmp_path: Path) -> None:
    """Verifies every valid row is validated, batched and inserted."""
    parquet_path = make_parquet(tmp_path, ["2024-01-01", "2024-02-01", "2024-03-01"])
    client = FakeClient(PRODUCTS_SPECS)

    summary = load_table("products", parquet_path, client, batch_size=2)

    assert summary == LoadSummary(rows_read=3, rows_loaded=3, failures=[])
    assert sum(len(batch) for batch in client.inserted_batches) == 3


def test_load_table_skips_invalid_rows_and_records_the_failure(tmp_path: Path) -> None:
    """Verifies a bad row is skipped, logged in the summary, and the rest still loads."""
    parquet_path = make_parquet(tmp_path, ["2024-01-01", "not-a-date", "2024-03-01"])
    client = FakeClient(PRODUCTS_SPECS)

    summary = load_table("products", parquet_path, client, batch_size=10)

    assert summary.rows_read == 3
    assert summary.rows_loaded == 2
    assert summary.rows_failed == 1
    assert "opening_date" in summary.failures[0].reason
    assert summary.failures[0].row_number == 2


def test_load_table_strict_mode_raises_on_first_invalid_row(tmp_path: Path) -> None:
    """Verifies --strict stops the load instead of skipping the bad row."""
    parquet_path = make_parquet(tmp_path, ["not-a-date"])
    client = FakeClient(PRODUCTS_SPECS)

    with pytest.raises(RowValidationError):
        load_table("products", parquet_path, client, batch_size=10, strict=True)

    assert client.inserted_batches == []


class ConnectionFakeClient(FakeClient):
    """Stands in for NeonClient as a context manager, logging its lifecycle in order."""

    def __init__(self, events: list[str]) -> None:
        """Serves the products specs and logs every event into the shared `events` list."""
        super().__init__(PRODUCTS_SPECS)
        self._events = events

    def __enter__(self) -> "ConnectionFakeClient":
        """Logs the connection opening and returns itself."""
        self._events.append("open")
        return self

    def __exit__(self, *exc_info: object) -> bool:
        """Logs the connection closing and never suppresses exceptions."""
        self._events.append("close")
        return False

    def truncate_table(self, table_name: str) -> None:
        """Logs the truncation with the table it targeted."""
        self._events.append(f"truncate {table_name}")

    def insert_rows(self, statement: str, rows: list[tuple]) -> None:
        """Logs each inserted batch by its size."""
        self._events.append(f"insert {len(rows)}")


@pytest.fixture
def connection_events(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Replaces NeonClient in the loader with a fake and returns its event log."""
    events: list[str] = []
    monkeypatch.setattr(loader, "NeonClient", lambda: ConnectionFakeClient(events))
    return events


def test_run_table_load_truncates_before_inserting_when_requested(
    tmp_path: Path, connection_events: list[str]
) -> None:
    """Verifies --truncate empties the table first, so a retry cannot duplicate rows."""
    parquet_path = make_parquet(tmp_path, ["2024-01-01", "2024-02-01"])

    summary = run_table_load("products", parquet_path, truncate=True)

    assert summary == LoadSummary(rows_read=2, rows_loaded=2, failures=[])
    assert connection_events == ["open", "truncate products", "insert 2", "close"]


def test_run_table_load_keeps_existing_rows_by_default(
    tmp_path: Path, connection_events: list[str]
) -> None:
    """Verifies a load without --truncate never touches the rows already in the table."""
    parquet_path = make_parquet(tmp_path, ["2024-01-01"])

    run_table_load("products", parquet_path)

    assert connection_events == ["open", "insert 1", "close"]


def test_run_table_load_closes_the_connection_when_the_load_fails(
    tmp_path: Path, connection_events: list[str]
) -> None:
    """Verifies a strict-mode failure still releases the database connection."""
    parquet_path = make_parquet(tmp_path, ["2024-01-01", "not-a-date"])

    with pytest.raises(RowValidationError):
        run_table_load("products", parquet_path, strict=True)

    assert connection_events[0] == "open"
    assert connection_events[-1] == "close"


def test_run_table_load_uses_the_default_batch_size(
    tmp_path: Path, connection_events: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifies callers that omit batch_size get the loader's documented default."""
    batch_sizes = []
    monkeypatch.setattr(
        loader,
        "load_table",
        lambda table, path, client, batch_size, strict: batch_sizes.append(batch_size)
        or LoadSummary(rows_read=0, rows_loaded=0),
    )

    run_table_load("products", make_parquet(tmp_path, ["2024-01-01"]))

    assert batch_sizes == [DEFAULT_BATCH_SIZE]
