"""Understands the dataset layout of the bucket: `<dataset>/year=YYYY/month=MM/day=DD/<file>`.

Exists to turn a flat list of file names into datasets (the main concept of each
file), to find which daily files are missing, and to select files by date range,
without touching S3. Consumed by `krtr/database/s3/client.py`.
"""

import calendar
import logging
import re
from collections import defaultdict
from datetime import date, timedelta

from krtr.database.s3.artifacts import DatasetSummary

logger = logging.getLogger(__name__)

PARTITION_PATTERN = re.compile(
    r"^(?P<dataset>[^/]+)/year=(?P<year>\d{4})/month=(?P<month>\d{2})/day=(?P<day>\d{2})/"
)


def parse_partition(file_name: str) -> tuple[str, date] | None:
    """Extracts the dataset name and partition date from a partitioned file name.

    Exists so every other function agrees on what a partitioned file looks like;
    files that are not partitioned (e.g. `customers.csv`) return None.

    Args:
        file_name: File name relative to the bucket root, e.g.
            `complaints/year=2024/month=09/day=11/complaints_20240911.csv`.

    Returns:
        tuple[str, date] | None: (dataset name, partition date), or None if the
            name is not date-partitioned or holds an impossible date.
    """
    match = PARTITION_PATTERN.match(file_name)
    if match is None:
        return None
    try:
        partition_date = date(int(match["year"]), int(match["month"]), int(match["day"]))
    except ValueError:
        logger.warning("Ignoring partition with an invalid date: %s", file_name)
        return None
    return match["dataset"], partition_date


def summarize_datasets(file_names: list[str]) -> list[DatasetSummary]:
    """Groups file names into datasets, reporting date coverage and missing days.

    Exists to answer "what can I download?" from a single bucket listing.

    Args:
        file_names: File names relative to the bucket root.

    Returns:
        list[DatasetSummary]: one summary per dataset, sorted by name. A
            partitioned dataset covers the days between its first and last
            files; days without a file are reported as missing.
    """
    dates_by_dataset: dict[str, list[date]] = defaultdict(list)
    summaries: dict[str, DatasetSummary] = {}
    for file_name in file_names:
        parsed = parse_partition(file_name)
        if parsed is None:
            summaries[file_name] = DatasetSummary(
                name=file_name, is_partitioned=False, file_count=1
            )
            continue
        dates_by_dataset[parsed[0]].append(parsed[1])
    for dataset, dates in dates_by_dataset.items():
        summaries[dataset] = _summarize_partitioned(dataset, dates)
    return [summaries[name] for name in sorted(summaries)]


def _summarize_partitioned(dataset: str, dates: list[date]) -> DatasetSummary:
    """Builds the summary of one date-partitioned dataset.

    Exists to keep the missing-day computation in one place.

    Args:
        dataset: The dataset name.
        dates: The partition date of every file in the dataset.

    Returns:
        DatasetSummary: file count, first/last date and missing days.
    """
    first_date, last_date = min(dates), max(dates)
    present = set(dates)
    days_in_range = (first_date + timedelta(days=offset) for offset in range(_span(dates)))
    return DatasetSummary(
        name=dataset,
        is_partitioned=True,
        file_count=len(dates),
        first_date=first_date,
        last_date=last_date,
        missing_dates=[day for day in days_in_range if day not in present],
    )


def _span(dates: list[date]) -> int:
    """Counts the calendar days from the earliest to the latest date, inclusive.

    Exists to keep `_summarize_partitioned` short and readable.

    Args:
        dates: The dates to measure; must not be empty.

    Returns:
        int: number of days in the inclusive range.
    """
    return (max(dates) - min(dates)).days + 1


def resolve_date_range(
    start: date | None, end: date | None, year: int | None, month: date | None
) -> tuple[date | None, date | None]:
    """Turns the user's date options into one inclusive (start, end) range.

    Exists so `--start/--end`, `--year` and `--month` behave consistently and
    conflicting options fail fast.

    Args:
        start: Inclusive first day, if given.
        end: Inclusive last day, if given.
        year: A whole calendar year, if given.
        month: Any day within the wanted month, if given.

    Returns:
        tuple[date | None, date | None]: inclusive bounds; None means unbounded.

    Raises:
        ValueError: if options are combined (`--year`, `--month`, or
            `--start/--end`) or `start` is after `end`.
    """
    selectors = [bool(start or end), year is not None, month is not None]
    if sum(selectors) > 1:
        raise ValueError("Use only one of --start/--end, --year or --month")
    if year is not None:
        return date(year, 1, 1), date(year, 12, 31)
    if month is not None:
        last_day = calendar.monthrange(month.year, month.month)[1]
        return month.replace(day=1), month.replace(day=last_day)
    if start and end and start > end:
        raise ValueError(f"--start ({start}) is after --end ({end})")
    return start, end


def select_dataset_files(
    file_names: list[str], dataset: str, start: date | None, end: date | None
) -> list[str]:
    """Selects the files of one dataset that fall inside a date range.

    Exists so downloads fetch only the days the user asked for.

    Args:
        file_names: File names relative to the bucket root.
        dataset: The dataset name (a folder like `complaints`, or a single
            file like `customers.csv`).
        start: Inclusive first day, or None for no lower bound.
        end: Inclusive last day, or None for no upper bound.

    Returns:
        list[str]: the matching file names, in input order.

    Raises:
        ValueError: if a date range is given for a dataset that is a single file.
    """
    selected = []
    for file_name in file_names:
        parsed = parse_partition(file_name)
        if parsed is None and file_name == dataset:
            if start or end:
                raise ValueError(f"Dataset '{dataset}' is not partitioned by date")
            selected.append(file_name)
        elif parsed is not None and parsed[0] == dataset and _within(parsed[1], start, end):
            selected.append(file_name)
    return selected


def _within(day: date, start: date | None, end: date | None) -> bool:
    """Checks whether a day lies inside an optional inclusive range.

    Exists to keep the bound checks out of `select_dataset_files`.

    Args:
        day: The day to test.
        start: Inclusive lower bound, or None.
        end: Inclusive upper bound, or None.

    Returns:
        bool: True if the day is within the bounds.
    """
    return (start is None or day >= start) and (end is None or day <= end)
