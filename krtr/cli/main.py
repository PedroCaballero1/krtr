"""Defines the root Typer application for the krtr CLI.

Exists to give every vertical package under `krtr/` a single, well-known
place to register its user-facing commands, and to centralize CLI-wide
concerns (logging setup, global options) instead of duplicating them per
command. Consumed by `krtr/cli/__init__.py`, which re-exports `app` for the
console entrypoint, and by tests under `tests/cli/`.

As verticals grow their own CLI commands, they get their own module here
mirroring the vertical's name (e.g. `krtr/database/` -> `krtr/cli/database.py`
or `krtr/cli/database/`), registered on `app` via `app.add_typer(...)`.
"""

import logging
from importlib.metadata import version as get_installed_version

import typer

from krtr.cli.back import back_app
from krtr.cli.compute import compute_app
from krtr.cli.database import database_app

app = typer.Typer(name="krtr", help="krtr command-line interface.", no_args_is_help=True)
app.add_typer(back_app, name="back")
app.add_typer(compute_app, name="compute")
app.add_typer(database_app, name="database")
logger = logging.getLogger(__name__)


@app.callback()
def configure_logging(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging."),
) -> None:
    """Configures logging once, before any command runs.

    Exists because this repository's logging convention requires handler
    configuration to happen exactly once, in the CLI entrypoint, so every
    vertical's `logging.getLogger(__name__)` calls produce consistent,
    step-by-step output; useful for every command invoked through this CLI.

    Args:
        verbose: When True, sets the log level to DEBUG instead of INFO.

    Returns:
        None.
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,
    )
    logger.debug("Logging configured at level %s", logging.getLevelName(log_level))


@app.command(name="version")
def show_version() -> None:
    """Prints the installed krtr package version.

    Exists so users and scripts can check which version of krtr is
    installed without importing the package directly; useful for bug
    reports and version-gated automation.

    Args:
        None.

    Returns:
        None.
    """
    installed_version = get_installed_version("krtr")
    logger.info("Resolved installed krtr version: %s", installed_version)
    typer.echo(installed_version)


if __name__ == "__main__":
    app()
