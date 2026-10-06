"""Tests `krtr back security credentials generate`: it runs the generator and fails cleanly."""

from pathlib import Path

import polars as pl
from typer.testing import CliRunner

from krtr.cli.main import app

runner = CliRunner()


def write_customers(directory: Path) -> Path:
    """Writes 120 Active customers: enough for the default 50 + 50 samples."""
    path = directory / "customers.parquet"
    pl.DataFrame(
        {
            "customer_id": [f"CLI-{number:012d}" for number in range(120)],
            "customer_status": ["Active"] * 120,
        }
    ).write_parquet(path)
    return path


def test_generate_writes_the_samples_and_user_files(tmp_path: Path) -> None:
    """The command produces the jury and QA CSVs and the Keycloak files."""
    output = tmp_path / "credentials"
    arguments = ["back", "security", "credentials", "generate"]
    options = ["--source", str(write_customers(tmp_path)), "--output", str(output), "--seed", "3"]

    result = runner.invoke(app, [*arguments, *options, "--workers", "2"])

    assert result.exit_code == 0, result.output
    assert (output / "jury_credentials.csv").read_text().count("\n") == 51
    assert (output / "qa_credentials.csv").read_text().count("\n") == 51
    assert len(list((output / "import").glob("krtr-users-*.json"))) == 1


def test_a_missing_source_exits_with_an_error(tmp_path: Path) -> None:
    """A wrong path must fail with exit code 1, not a traceback."""
    result = runner.invoke(
        app,
        ["back", "security", "credentials", "generate", "--source", str(tmp_path / "none.parquet")],
    )

    assert result.exit_code == 1
