"""Locates a table's source file and converts CSV to Parquet if needed.

Exists to implement the file-format contract shared by every table loaded
into Neon: Parquet is the default working format, a same-named CSV drop-in
is converted once, and the conversion is cached to disk so future runs skip
straight to the Parquet file. Consumed by the `krtr database neon load` CLI
command.
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
        return _convert_csv_to_parquet(csv_path, parquet_path)
    if force_convert:
        raise FileNotFoundError(f"--force-convert given but no CSV found at '{csv_path}'")
    raise FileNotFoundError(
        f"No source found for '{table_name}': expected '{parquet_path}' or '{csv_path}'"
    )


def _convert_csv_to_parquet(csv_path: Path, parquet_path: Path) -> Path:
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
