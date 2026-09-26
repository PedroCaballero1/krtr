"""Tests the structured values produced by Neon table loaders."""

from krtr.database.neon.artifacts import LoadSummary, ValidationFailure


def test_rows_failed_counts_the_failures_list() -> None:
    """Verifies rows_failed reflects the number of recorded failures, not rows_read."""
    summary = LoadSummary(
        rows_read=10,
        rows_loaded=8,
        failures=[
            ValidationFailure(row_number=3, reason="bad date"),
            ValidationFailure(row_number=7, reason="missing id"),
        ],
    )

    assert summary.rows_failed == 2


def test_rows_failed_is_zero_when_no_failures_were_recorded() -> None:
    """Verifies a clean load reports zero failures without passing the field explicitly."""
    summary = LoadSummary(rows_read=5, rows_loaded=5)

    assert summary.rows_failed == 0
