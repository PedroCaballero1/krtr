"""Exposes the krtr CLI's Typer application to callers outside this package.

Exists so callers (a console-script entrypoint, `python -m krtr.cli.main`,
or tests under `tests/cli/`) can depend on `krtr.cli.app` without knowing
the Typer instance actually lives in `krtr.cli.main`.
"""

from krtr.cli.main import app

__all__ = ["app"]
