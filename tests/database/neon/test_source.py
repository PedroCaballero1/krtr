"""Tests resolving a table's Parquet source, converting a CSV when needed."""

from pathlib import Path

import polars as pl
import pytest

from krtr.database.neon.source import resolve_table_source


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
