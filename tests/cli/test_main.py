"""Tests the krtr CLI's root Typer application.

Exists to verify the CLI's actual observable behavior — the printed
version and the effect of --verbose on logging — rather than merely that
commands execute without raising.
"""

import logging
from importlib.metadata import version as get_installed_version

from typer.testing import CliRunner

from krtr.cli.main import app

runner = CliRunner()


def test_version_command_prints_the_installed_package_version() -> None:
    """Verifies `krtr version` prints the exact installed version string.

    Guards against the command drifting from the real installed
    distribution (e.g. printing a hardcoded or stale version).
    """
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == get_installed_version("krtr")


def test_verbose_flag_sets_root_logger_to_debug_level() -> None:
    """Verifies --verbose actually raises the log level to DEBUG.

    Guards against the CLI's global logging setup silently ignoring the
    flag, which would make `--verbose` a no-op for users diagnosing issues.
    """
    root_logger = logging.getLogger()
    original_level = root_logger.level

    try:
        result = runner.invoke(app, ["--verbose", "version"])
        assert result.exit_code == 0
        assert root_logger.level == logging.DEBUG
    finally:
        root_logger.setLevel(original_level)


def test_default_invocation_keeps_root_logger_at_info_level() -> None:
    """Verifies the default (non-verbose) invocation sets INFO, not DEBUG.

    Without this, a regression that always enables DEBUG logging would
    pass the --verbose test above without being caught.
    """
    root_logger = logging.getLogger()
    original_level = root_logger.level

    try:
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert root_logger.level == logging.INFO
    finally:
        root_logger.setLevel(original_level)
