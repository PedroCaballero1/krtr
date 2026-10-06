"""Defines the `krtr back deploy` CLI commands (task 6.1).

Exists to expose the deploy tooling as thin commands: `push-secrets` creates or updates the
krtr-web app's three Modal secrets from `.env`. Consumed by `krtr/cli/back/__init__.py`.
"""

import logging

import typer

from krtr.back.deploy.secrets import push_deploy_secrets
from krtr.compute.modal.errors import RemoteExecutionError

logger = logging.getLogger(__name__)

deploy_app = typer.Typer(name="deploy", help="krtr-web on Modal.", no_args_is_help=True)


@deploy_app.command(name="push-secrets")
def push_secrets() -> None:
    """Creates or updates the krtr-web, krtr-auth and krtr-jobs Modal secrets from `.env`.

    Args:
        None.

    Returns:
        None.
    """
    try:
        pushed = push_deploy_secrets()
    except (ValueError, RemoteExecutionError) as error:
        logger.error("%s", error)
        raise typer.Exit(code=1) from error
    logger.info("Pushed %d secrets", len(pushed))
