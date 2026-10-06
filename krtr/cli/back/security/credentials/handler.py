"""Defines the `krtr back security credentials` CLI commands (tasks 3.4 and 3.5).

Exists to expose the credentials tooling as thin commands: `generate` creates every customer's
password, the Keycloak user files and the jury and QA samples; `import` loads those users into
the local Keycloak, or (`--remote`) into the production one on Modal. Consumed by
`krtr/cli/back/security/__init__.py`, which registers `credentials_app`.
"""

import logging
from pathlib import Path

import httpx
import typer

from krtr.back.security.credentials.config import (
    DEFAULT_OUTPUT_DIRECTORY,
    DEFAULT_SOURCE,
    IMPORT_VOLUME,
    CredentialsConfig,
)
from krtr.back.security.credentials.generator import generate_credentials
from krtr.back.security.credentials.importer import (
    DEFAULT_CHUNK_SIZE,
    DEFAULT_PARALLEL_REQUESTS,
    import_users,
    users_files,
)
from krtr.back.security.credentials.remote import (
    KeycloakIsServing,
    ModalAuthImportTarget,
    import_on_modal,
)
from krtr.back.security.keycloak.admin_client import KeycloakAdminClient
from krtr.back.security.keycloak.artifacts import PartialImportResult
from krtr.back.security.keycloak.config import KeycloakAdminConfig
from krtr.compute.modal.errors import MODAL_MISSING_HINT
from krtr.compute.modal.volume import ModalStagingVolume

logger = logging.getLogger(__name__)

DEFAULT_IMPORT_SOURCE = DEFAULT_OUTPUT_DIRECTORY / "import"
LOCAL_IMPORT_TIMEOUT_SECONDS = 600  # A batch of 1,000 users is slow against Neon from afar.

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


@credentials_app.command(name="import")
def import_command(
    source: Path = typer.Option(DEFAULT_IMPORT_SOURCE, help="Folder with krtr-users-<n>.json."),
    remote: bool = typer.Option(
        False, "--remote", help="Import into the production Keycloak on Modal (auth_import)."
    ),
    force: bool = typer.Option(
        False, "--force", help="With --remote: import even while the auth function is running."
    ),
    chunk_size: int = typer.Option(DEFAULT_CHUNK_SIZE, help="Users per request (local only)."),
    parallel: int = typer.Option(DEFAULT_PARALLEL_REQUESTS, help="Requests at once (local only)."),
) -> None:
    """Imports the generated users into Keycloak, skipping those already there.

    Locally it needs the docker compose Keycloak running and KRTR_KEYCLOAK_ADMIN_PASSWORD in
    `.env`. With --remote it needs the deployed krtr-web app and the `modal` extra.

    Args:
        source: The folder the generator wrote the users files to.
        remote: Whether to import on Modal instead of locally.
        force: Whether to import on Modal while the serving Keycloak is up.
        chunk_size: Users per partialImport request, locally.
        parallel: How many requests run at once, locally.

    Returns:
        None.
    """
    try:
        files = users_files(source)
        if remote:
            result = _import_remotely(files, force)
        else:
            result = _import_locally(files, chunk_size, parallel)
    except (FileNotFoundError, ValueError, KeycloakIsServing, httpx.HTTPError) as error:
        logger.error("%s", error)
        raise typer.Exit(code=1) from error
    logger.info("%d users added, %d already there", result.added, result.skipped)


def _import_locally(files: list[Path], chunk_size: int, parallel: int) -> PartialImportResult:
    """Imports the files into the docker compose Keycloak.

    Args:
        files: The users files.
        chunk_size: Users per request.
        parallel: Requests at once.

    Returns:
        PartialImportResult: the totals.
    """
    with httpx.Client(timeout=LOCAL_IMPORT_TIMEOUT_SECONDS) as http_client:
        admin = KeycloakAdminClient(KeycloakAdminConfig.from_environment(), http_client)
        return import_users(admin, files, chunk_size, parallel)


def _import_remotely(files: list[Path], force: bool) -> PartialImportResult:
    """Imports the files into the production Keycloak through the auth_import function.

    Args:
        files: The users files.
        force: Whether to import while `auth` is running.

    Returns:
        PartialImportResult: the totals.

    Raises:
        ValueError: if the `modal` extra is not installed.
    """
    try:
        volume = ModalStagingVolume(IMPORT_VOLUME)
        target = ModalAuthImportTarget()
    except ImportError as error:
        raise ValueError(MODAL_MISSING_HINT) from error
    return import_on_modal(files, volume, target, force=force)
