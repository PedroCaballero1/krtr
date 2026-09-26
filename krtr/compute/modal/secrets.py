"""Copies the allowed environment variables from `.env` into the Modal secret.

Exists so the container receives the credentials it needs (the Neon connection
string) without anyone creating the secret by hand in the Modal dashboard. Only
the variables in `ForwardedSecretVariable` are ever sent; the whole `.env` never
is. Consumed by the `krtr compute modal secrets sync` command.
"""

import logging
import os

from dotenv import load_dotenv

from krtr.compute.modal.config import ForwardedSecretVariable
from krtr.compute.modal.errors import MODAL_MISSING_HINT, RemoteExecutionError

logger = logging.getLogger(__name__)


def read_forwarded_variables() -> dict[str, str]:
    """Reads the allowed variables from the environment and any `.env` file.

    Exists so the set of values that leave the machine is decided in one
    place: only `ForwardedSecretVariable` members, however many other
    variables (AWS keys, Modal tokens) the environment holds.

    Returns:
        dict[str, str]: each allowed variable's name and value.

    Raises:
        ValueError: if any allowed variable is missing or empty.
    """
    load_dotenv()
    values = {
        variable.value: os.environ.get(variable.value, "") for variable in ForwardedSecretVariable
    }
    missing = sorted(name for name, value in values.items() if not value)
    if missing:
        raise ValueError(f"Missing required environment variable(s): {', '.join(missing)}")
    return values


def push_secret(secret_name: str, values: dict[str, str]) -> None:
    """Creates the named Modal secret if needed and overwrites its values.

    Exists because `create(allow_existing=True)` keeps the old values of a
    secret that already exists, so a rotated password would never reach Modal;
    `update` is what actually overwrites them.

    Args:
        secret_name: Name of the Modal secret.
        values: Environment variable names and values to store in it.

    Returns:
        None.

    Raises:
        RemoteExecutionError: if the optional `modal` SDK is not installed.
    """
    try:
        import modal
    except ImportError as error:
        raise RemoteExecutionError(MODAL_MISSING_HINT) from error

    modal.Secret.objects.create(secret_name, values, allow_existing=True)
    secret = modal.Secret.from_name(secret_name)
    secret.hydrate()
    secret.update(values)


def sync_secret(secret_name: str) -> list[str]:
    """Copies the allowed variables from `.env` into the Modal secret.

    Exists as the single call behind `secrets sync`. Values are never logged,
    only the names of the variables synced.

    Args:
        secret_name: Name of the Modal secret.

    Returns:
        list[str]: the names of the variables stored in the secret.

    Raises:
        ValueError: if any allowed variable is missing or empty.
    """
    values = read_forwarded_variables()
    logger.info("Syncing %s to Modal secret '%s'", ", ".join(sorted(values)), secret_name)
    push_secret(secret_name, values)
    return sorted(values)
