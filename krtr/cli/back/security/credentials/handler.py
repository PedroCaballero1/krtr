"""Defines the `krtr back security credentials` CLI commands (task 3.4).

Exists to expose the credentials generator as a thin command: `generate` creates every
customer's password, the Keycloak user files and the jury and QA samples. Consumed by
`krtr/cli/back/security/__init__.py`, which registers `credentials_app`.
"""

import logging
from pathlib import Path

import typer

from krtr.back.security.credentials.config import (
    DEFAULT_OUTPUT_DIRECTORY,
    DEFAULT_SOURCE,
    CredentialsConfig,
)
from krtr.back.security.credentials.generator import generate_credentials

logger = logging.getLogger(__name__)

credentials_app = typer.Typer(
    name="credentials", help="Customer credentials (G6).", no_args_is_help=True
)


@credentials_app.command(name="generate")
def generate(
    source: Path = typer.Option(DEFAULT_SOURCE, help="Customers Parquet file."),
    output: Path = typer.Option(DEFAULT_OUTPUT_DIRECTORY, help="Where to write the credentials."),
    seed: int | None = typer.Option(None, help="Seed of the jury/QA draw; random if omitted."),
    workers: int | None = typer.Option(None, help="Hashing processes; one per CPU if omitted."),
    overwrite: bool = typer.Option(
        False, "--overwrite", help="Replace earlier credentials (changes every password)."
    ),
) -> None:
    """Generates every customer's password, the Keycloak user files and the samples.

    Args:
        source: The customers Parquet file.
        output: The output folder (git-ignored under data/).
        seed: The seed of the sample draw.
        workers: How many hashing processes.
        overwrite: Whether to replace an earlier run.

    Returns:
        None.
    """
    config = CredentialsConfig(source=source, output_directory=output, workers=workers)
    try:
        summary = generate_credentials(config, seed=seed, overwrite=overwrite)
    except (FileExistsError, FileNotFoundError, ValueError) as error:
        logger.error("%s", error)
        raise typer.Exit(code=1) from error
    for group, path in summary.samples.items():
        logger.info("%s credentials: %s", group.value, path)
    logger.info("Keycloak user files: %s (%d files)", summary.import_directory, summary.user_files)
