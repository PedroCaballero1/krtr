"""Builds and pushes the three Modal secrets of the krtr-web app (task 6.1).

Exists so production credentials go from `.env` to Modal without anyone typing them in the
dashboard, and only through an explicit allowlist: each secret gets exactly the variables its
functions need, derived from `.env`; the whole `.env` never leaves the machine and no value is
ever logged. Production-only secrets (the Keycloak admin password and the OIDC client secret)
are generated once into `.env` if missing. `modal` is imported only by `push_secret`, so this
module loads without the extra. Consumed by `krtr/cli/back/deploy/handler.py`.
"""

import base64
import logging
import os
import secrets
from enum import StrEnum
from pathlib import Path
from urllib.parse import quote, urlsplit

from dotenv import load_dotenv

from krtr.back.deploy.config import AUTH_PUBLIC_URL, WEB_PUBLIC_URL, DeploySecret
from krtr.compute.modal.secrets import push_secret

logger = logging.getLogger(__name__)

ENV_FILE = Path(".env")
APP_ROLE = "krtr_app"
KEYCLOAK_ROLE = "krtr_keycloak"
APP_DATABASE = "neondb"
KEYCLOAK_DATABASE = "keycloak"
KEYCLOAK_ADMIN = "admin"
POOLER_SUFFIX = "-pooler"


class SourceVariable(StrEnum):
    """The `.env` variables the secrets are built from."""

    NEON_ADMIN_URL = "NEON_DB_HOST"  # Production, pooled; only its host is used.
    APP_PASSWORD = "KRTR_APP_DB_PASSWORD"
    KEYCLOAK_PASSWORD = "KRTR_KEYCLOAK_DB_PASSWORD"
    TOKENS_KEY = "KRTR_TOKENS_KEY"
    EVENTS_KEY = "KRTR_EVENTS_KEY"
    MESSAGES_KEY = "KRTR_MESSAGES_KEY"
    PROD_CLIENT_SECRET = "KRTR_PROD_WEB_OIDC_CLIENT_SECRET"  # Generated if missing.
    PROD_ADMIN_PASSWORD = "KRTR_PROD_KEYCLOAK_ADMIN_PASSWORD"  # Generated if missing.


_GENERATED = (SourceVariable.PROD_CLIENT_SECRET, SourceVariable.PROD_ADMIN_PASSWORD)


def build_secret_values(environment: dict[str, str]) -> dict[DeploySecret, dict[str, str]]:
    """Derives each secret's variables from the source variables.

    Args:
        environment: The source variables, by name.

    Returns:
        dict[DeploySecret, dict[str, str]]: each secret's variables.

    Raises:
        ValueError: if a source variable is missing or empty.
    """
    missing = sorted(variable.value for variable in SourceVariable if not environment.get(variable))
    if missing:
        raise ValueError(f"Missing required environment variable(s): {', '.join(missing)}")
    pooler_host = urlsplit(environment[SourceVariable.NEON_ADMIN_URL]).hostname or ""
    app_url = _postgres_url(APP_ROLE, environment[SourceVariable.APP_PASSWORD], pooler_host)
    client_secret = environment[SourceVariable.PROD_CLIENT_SECRET]
    return {
        DeploySecret.WEB: {
            "NEON_DB_HOST": app_url,
            "KRTR_TOKENS_KEY": environment[SourceVariable.TOKENS_KEY],
            "KRTR_EVENTS_KEY": environment[SourceVariable.EVENTS_KEY],
            "KRTR_MESSAGES_KEY": environment[SourceVariable.MESSAGES_KEY],
            "KRTR_WEB_OIDC_CLIENT_SECRET": client_secret,
            "KRTR_PUBLIC_URL": WEB_PUBLIC_URL,
            "KRTR_AUTH_ORIGIN": AUTH_PUBLIC_URL,
        },
        DeploySecret.AUTH: {
            "KC_DB_URL": f"jdbc:postgresql://{_direct_host(pooler_host)}/{KEYCLOAK_DATABASE}"
            "?sslmode=require",
            "KC_DB_USERNAME": KEYCLOAK_ROLE,
            "KC_DB_PASSWORD": environment[SourceVariable.KEYCLOAK_PASSWORD],
            "KC_BOOTSTRAP_ADMIN_USERNAME": KEYCLOAK_ADMIN,
            "KC_BOOTSTRAP_ADMIN_PASSWORD": environment[SourceVariable.PROD_ADMIN_PASSWORD],
            "KRTR_WEB_OIDC_CLIENT_SECRET": client_secret,
        },
        DeploySecret.JOBS: {
            "NEON_DB_HOST": app_url,
            "KRTR_EVENTS_KEY": environment[SourceVariable.EVENTS_KEY],
            "KRTR_MESSAGES_KEY": environment[SourceVariable.MESSAGES_KEY],
        },
    }


def push_deploy_secrets(env_file: Path = ENV_FILE) -> dict[DeploySecret, list[str]]:
    """Generates the missing production secrets, then creates or updates the three secrets.

    Args:
        env_file: The `.env` file to read, and to append generated values to.

    Returns:
        dict[DeploySecret, list[str]]: each secret's variable names (never values).
    """
    load_dotenv(env_file)
    _generate_missing(env_file)
    values = build_secret_values(
        {variable.value: os.environ.get(variable, "") for variable in SourceVariable}
    )
    for secret, variables in values.items():
        push_secret(secret.value, variables)
        logger.info("Pushed Modal secret %s: %s", secret.value, ", ".join(sorted(variables)))
    return {secret: sorted(variables) for secret, variables in values.items()}


def _generate_missing(env_file: Path) -> None:
    """Appends a random value to `.env` for each production secret it lacks.

    Args:
        env_file: The `.env` file.

    Returns:
        None.
    """
    for variable in _GENERATED:
        if os.environ.get(variable):
            continue
        value = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")
        with env_file.open("a", encoding="utf-8") as file:
            file.write(f"\n{variable.value}={value}\n")
        os.environ[variable.value] = value
        logger.info("Generated %s into %s", variable.value, env_file)


def _postgres_url(role: str, password: str, host: str) -> str:
    """Builds the pooled connection string of the app database for a role.

    Args:
        role: The database role.
        password: Its password (URL-encoded here).
        host: The pooled host.

    Returns:
        str: the `postgresql://` URL with TLS and channel binding required.
    """
    credentials = f"{role}:{quote(password, safe='')}"
    return (
        f"postgresql://{credentials}@{host}/{APP_DATABASE}?sslmode=require&channel_binding=require"
    )


def _direct_host(pooler_host: str) -> str:
    """Returns the direct (non-pooled) host Keycloak needs, from the pooled one.

    Args:
        pooler_host: The `-pooler` host.

    Returns:
        str: the same endpoint without the pooler.
    """
    endpoint, _, domain = pooler_host.partition(".")
    return f"{endpoint.removesuffix(POOLER_SUFFIX)}.{domain}"
