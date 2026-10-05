"""Tests resolving a table's Parquet source, converting a CSV when needed."""

from pathlib import Path

import polars as pl
import pytest

from krtr.database.neon.source import resolve_partitioned_sources, resolve_table_source


def test_resolve_table_source_prefers_an_existing_parquet_file(tmp_path: Path) -> None:
    """Verifies an existing Parquet file is returned without touching any CSV."""
    parquet_path = tmp_path / "products.parquet"
    pl.DataFrame({"a": [1]}).write_parquet(parquet_path)
    (tmp_path / "products.csv").write_text("a\n1\n")

    result = resolve_table_source("products", tmp_path)

    assert result == parquet_path
    assert pl.read_parquet(parquet_path).to_dicts() == [{"a": 1}]


def test_resolve_table_source_converts_a_csv_when_no_parquet_exists(tmp_path: Path) -> None:
    """Verifies a lone CSV is converted to Parquet and the Parquet path is returned."""
    csv_path = tmp_path / "products.csv"
    csv_path.write_text("product_id,current_balance\nP1,10.50\n")

    result = resolve_table_source("products", tmp_path)

    assert result == tmp_path / "products.parquet"
    assert pl.read_parquet(result).to_dicts() == [{"product_id": "P1", "current_balance": 10.5}]


def test_resolve_table_source_caches_the_converted_parquet(tmp_path: Path) -> None:
    """Verifies a second call reuses the cached Parquet instead of reconverting."""
    csv_path = tmp_path / "products.csv"
    csv_path.write_text("product_id\nP1\n")
    resolve_table_source("products", tmp_path)
    csv_path.unlink()

    result = resolve_table_source("products", tmp_path)

    assert result == tmp_path / "products.parquet"


def test_resolve_table_source_force_convert_overwrites_cached_parquet(tmp_path: Path) -> None:
    """Verifies --force-convert re-reads the CSV even when a Parquet is already cached."""
    parquet_path = tmp_path / "products.parquet"
    pl.DataFrame({"product_id": ["stale"]}).write_parquet(parquet_path)
    (tmp_path / "products.csv").write_text("product_id\nfresh\n")

    result = resolve_table_source("products", tmp_path, force_convert=True)

    assert pl.read_parquet(result).to_dicts() == [{"product_id": "fresh"}]


def test_resolve_table_source_raises_when_neither_file_exists(tmp_path: Path) -> None:
    """Verifies a clear error names both paths that were expected."""
    with pytest.raises(FileNotFoundError, match="products.parquet"):
        resolve_table_source("products", tmp_path)


def test_resolve_table_source_force_convert_raises_without_a_csv(tmp_path: Path) -> None:
    """Verifies --force-convert with no CSV present fails instead of silently loading nothing."""
    pl.DataFrame({"product_id": ["x"]}).write_parquet(tmp_path / "products.parquet")

    with pytest.raises(FileNotFoundError, match="force-convert"):
        resolve_table_source("products", tmp_path, force_convert=True)


def _write_partition(tmp_path: Path, day: str) -> Path:
    """Writes one daily transactions.csv under the year=/month=/day= layout."""
    partition_dir = tmp_path / "transactions" / f"year=2026/month=01/day={day}"
    partition_dir.mkdir(parents=True)
    csv_path = partition_dir / f"transactions_2026-01-{day}.csv"
    csv_path.write_text("transaction_id,amount\nT1,10.50\n")
    return csv_path


def test_resolve_partitioned_sources_converts_every_daily_csv(tmp_path: Path) -> None:
    """Verifies every daily CSV under the dataset directory is found and converted."""
    _write_partition(tmp_path, "01")
    _write_partition(tmp_path, "02")

    result = resolve_partitioned_sources("transactions", tmp_path)

    assert result == [
        tmp_path / "transactions" / "year=2026/month=01/day=01/transactions_2026-01-01.parquet",
        tmp_path / "transactions" / "year=2026/month=01/day=02/transactions_2026-01-02.parquet",
    ]
    assert all(path.exists() for path in result)


def test_resolve_partitioned_sources_sorts_by_path_which_sorts_by_date(tmp_path: Path) -> None:
    """Verifies files come back oldest-first, regardless of filesystem listing order."""
    _write_partition(tmp_path, "02")
    _write_partition(tmp_path, "01")

    result = resolve_partitioned_sources("transactions", tmp_path)

    assert [path.name for path in result] == [
        "transactions_2026-01-01.parquet",
        "transactions_2026-01-02.parquet",
    ]


def test_resolve_partitioned_sources_caches_each_converted_parquet(tmp_path: Path) -> None:
    """Verifies a second call reuses the cached Parquet files instead of reconverting."""
    csv_path = _write_partition(tmp_path, "01")
    resolve_partitioned_sources("transactions", tmp_path)
    csv_path.unlink()

    result = resolve_partitioned_sources("transactions", tmp_path)

    assert len(result) == 1
    assert result[0].exists()


def test_resolve_partitioned_sources_force_convert_overwrites_cached_parquet(
    tmp_path: Path,
) -> None:
    """Verifies --force-convert re-reads every CSV even when Parquet is already cached."""
    csv_path = _write_partition(tmp_path, "01")
    parquet_path = csv_path.with_suffix(".parquet")
    pl.DataFrame({"transaction_id": ["stale"]}).write_parquet(parquet_path)

    result = resolve_partitioned_sources("transactions", tmp_path, force_convert=True)

    assert pl.read_parquet(result[0]).to_dicts() == [{"transaction_id": "T1", "amount": 10.5}]


def test_resolve_partitioned_sources_raises_when_no_daily_files_exist(tmp_path: Path) -> None:
    """Verifies a clear error names the dataset directory that held nothing."""
    with pytest.raises(FileNotFoundError, match="transactions"):
        resolve_partitioned_sources("transactions", tmp_path)
