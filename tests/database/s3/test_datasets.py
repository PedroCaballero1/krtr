"""Tests dataset detection, missing-day reporting and date-range selection."""

from datetime import date

import pytest

from krtr.database.s3.datasets import (
    parse_partition,
    resolve_date_range,
    select_dataset_files,
    summarize_datasets,
)


def _daily(dataset: str, *days: str) -> list[str]:
    """Builds partitioned file names for the given `YYYYMMDD` days."""
    return [f"{dataset}/year={d[:4]}/month={d[4:6]}/day={d[6:]}/{dataset}_{d}.csv" for d in days]


def test_parse_partition_extracts_dataset_and_date() -> None:
    """Verifies the concept and the day are read from a partitioned path."""
    name = "complaints/year=2024/month=09/day=11/complaints_20240911.csv"

    assert parse_partition(name) == ("complaints", date(2024, 9, 11))


@pytest.mark.parametrize(
    "name", ["customers.csv", "x/year=2024/month=13/day=01/f.csv", "x/2024/09/11/f.csv"]
)
def test_parse_partition_returns_none_for_unpartitioned_or_invalid(name: str) -> None:
    """Verifies single files and impossible dates are not treated as partitions."""
    assert parse_partition(name) is None


def test_summarize_reports_coverage_and_missing_days() -> None:
    """Verifies a gap between the first and last file is reported as missing."""
    files = _daily("sends", "20240101", "20240102", "20240105", "20240106") + ["customers.csv"]

    sends, customers = summarize_datasets(files)[1], summarize_datasets(files)[0]

    assert customers.name == "customers.csv"
    assert customers.is_partitioned is False
    assert (sends.name, sends.file_count) == ("sends", 4)
    assert (sends.first_date, sends.last_date) == (date(2024, 1, 1), date(2024, 1, 6))
    assert sends.missing_dates == [date(2024, 1, 3), date(2024, 1, 4)]


def test_summarize_complete_dataset_has_no_missing_days() -> None:
    """Verifies a gapless dataset reports nothing missing."""
    summary = summarize_datasets(_daily("tx", "20240228", "20240229", "20240301"))[0]

    assert summary.missing_dates == []


def test_select_filters_dataset_and_inclusive_date_range() -> None:
    """Verifies only the requested dataset's files inside the inclusive range are chosen."""
    files = _daily("a", "20240101", "20240102", "20240103") + _daily("b", "20240102")

    selected = select_dataset_files(files, "a", date(2024, 1, 2), date(2024, 1, 3))

    assert selected == _daily("a", "20240102", "20240103")


def test_select_single_file_dataset_and_rejects_dates_for_it() -> None:
    """Verifies single files download whole, and dates on them are an error."""
    assert select_dataset_files(["customers.csv"], "customers.csv", None, None) == ["customers.csv"]
    with pytest.raises(ValueError, match="not partitioned"):
        select_dataset_files(["customers.csv"], "customers.csv", date(2024, 1, 1), None)


def test_resolve_year_and_month_cover_the_whole_period() -> None:
    """Verifies --year and --month expand to first and last day, including leap February."""
    assert resolve_date_range(None, None, 2025, None) == (date(2025, 1, 1), date(2025, 12, 31))
    assert resolve_date_range(None, None, None, date(2024, 2, 10)) == (
        date(2024, 2, 1),
        date(2024, 2, 29),
    )


def test_resolve_passes_through_start_and_end() -> None:
    """Verifies explicit bounds (or none) are returned unchanged."""
    assert resolve_date_range(date(2024, 1, 1), None, None, None) == (date(2024, 1, 1), None)
    assert resolve_date_range(None, None, None, None) == (None, None)


def test_resolve_rejects_conflicting_or_reversed_options() -> None:
    """Verifies mixed selectors and a start after the end fail fast."""
    with pytest.raises(ValueError, match="only one"):
        resolve_date_range(date(2024, 1, 1), None, 2024, None)
    with pytest.raises(ValueError, match="only one"):
        resolve_date_range(None, None, 2024, date(2024, 1, 1))
    with pytest.raises(ValueError, match="after"):
        resolve_date_range(date(2024, 2, 1), date(2024, 1, 1), None, None)
