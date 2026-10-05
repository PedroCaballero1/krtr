"""Locates a table's source file(s) and converts CSV to Parquet if needed.

Exists to implement the file-format contract shared by every table loaded
into Neon: Parquet is the default working format, a same-named CSV drop-in
is converted once, and the conversion is cached to disk so future runs skip
straight to the Parquet file. Handles both a single-file table
(`resolve_table_source`) and a dataset partitioned into daily files
(`resolve_partitioned_sources`). Consumed by the `krtr database neon load`
and `load-dataset` CLI commands.
"""

import logging
from pathlib import Path

import polars as pl

logger = logging.getLogger(__name__)


def resolve_table_source(
    table_name: str, source_directory: Path, force_convert: bool = False
) -> Path:
    """Finds a table's Parquet file, converting a same-named CSV if needed.

    Looks for `<table_name>.parquet` first. If it is missing (or
    `force_convert` is True), it looks for `<table_name>.csv` and converts
    it, overwriting any previously cached Parquet file.

    Args:
        table_name: Name of the table being loaded, e.g. `products`.
        source_directory: Directory searched for `<table_name>.parquet` /
            `<table_name>.csv`.
        force_convert: When True, always reconvert from the CSV even if a
            cached Parquet file already exists.

    Returns:
        Path: the Parquet file to load.

    Raises:
        FileNotFoundError: if neither file exists, or if `force_convert` is
            True but the CSV is missing.
    """
    parquet_path = source_directory / f"{table_name}.parquet"
    csv_path = source_directory / f"{table_name}.csv"
    if not force_convert and parquet_path.exists():
        logger.info("Found Parquet source at %s", parquet_path)
        return parquet_path
    if csv_path.exists():
        return convert_csv_to_parquet(csv_path, parquet_path)
    if force_convert:
        raise FileNotFoundError(f"--force-convert given but no CSV found at '{csv_path}'")
    raise FileNotFoundError(
        f"No source found for '{table_name}': expected '{parquet_path}' or '{csv_path}'"
    )


def resolve_partitioned_sources(
    table_name: str, source_directory: Path, force_convert: bool = False
) -> list[Path]:
    """Finds every daily CSV of a partitioned dataset, converting each to Parquet.

    Looks for `<table_name>_*.csv` files anywhere under
    `source_directory/<table_name>/`, the `year=YYYY/month=MM/day=DD` layout
    that `krtr database s3 download-dataset` preserves when it downloads a
    partitioned dataset (e.g. `transactions`). Each file is converted to a
    same-named Parquet file next to it, cached the same way
    `resolve_table_source` caches a single-file table's Parquet.

    Args:
        table_name: Name of the partitioned dataset, e.g. `transactions`.
        source_directory: Directory holding `<table_name>/`.
        force_convert: When True, reconvert every CSV even if a cached
            Parquet file already exists next to it.

    Returns:
        list[Path]: the Parquet file of each daily partition, sorted by path
            (which sorts by date, since partitions are named
            `year=YYYY/month=MM/day=DD`).

    Raises:
        FileNotFoundError: if `source_directory/<table_name>/` holds neither a
            `<table_name>_*.csv` nor a previously cached `<table_name>_*.parquet`.
    """
    dataset_directory = source_directory / table_name
    stems = {path.with_suffix("") for path in dataset_directory.rglob(f"{table_name}_*.csv")}
    stems |= {path.with_suffix("") for path in dataset_directory.rglob(f"{table_name}_*.parquet")}
    if not stems:
        raise FileNotFoundError(f"No '{table_name}_*.csv' files found under '{dataset_directory}'")
    return [
        _resolve_partition_parquet(stem.with_suffix(".csv"), force_convert)
        for stem in sorted(stems)
    ]


def _resolve_partition_parquet(csv_path: Path, force_convert: bool) -> Path:
    """Converts one partition's CSV to Parquet, reusing a cached file when valid.

    Exists to keep `resolve_partitioned_sources` a short, readable loop.

    Args:
        csv_path: The partition's CSV file.
        force_convert: When True, reconvert even if a cached Parquet exists.

    Returns:
        Path: the Parquet file for this partition.
    """
    parquet_path = csv_path.with_suffix(".parquet")
    if not force_convert and parquet_path.exists():
        return parquet_path
    return convert_csv_to_parquet(csv_path, parquet_path)


def convert_csv_to_parquet(csv_path: Path, parquet_path: Path) -> Path:
    """Converts a CSV file to Parquet using polars and caches it on disk.

    Exists so the conversion only runs once per CSV; later runs find the
    cached `.parquet` file and skip straight to it.

    Args:
        csv_path: The CSV file to convert.
        parquet_path: Destination path for the converted Parquet file.

    Returns:
        Path: `parquet_path`, now written to disk.
    """
    logger.info("Converting %s to %s (cached for future runs)", csv_path, parquet_path)
    pl.read_csv(csv_path, try_parse_dates=True).write_parquet(parquet_path)
    return parquet_path
