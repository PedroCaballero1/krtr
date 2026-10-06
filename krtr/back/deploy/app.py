"""Defines the krtr-web Modal app: the web, Keycloak, the user import and the daily purge (D21).

Exists so one `uv run --env-file .env modal deploy krtr/back/deploy/app.py` publishes everything:

- `web` (task 6.2): the FastAPI app and the SPA, from `create_served_app`, at
  `https://<ws>--krtr.modal.run`;
- `auth` (task 6.3): Keycloak on 127.0.0.1:8081 behind the gateway of task 3.7, at
  `https://<ws>--krtr-auth.modal.run`;
- `auth_import` (task 6.4): imports the users files staged on the `krtr-credentials-import`
  Volume through Keycloak's admin API, never exposed to the internet;
- `purge_events` (task 6.5): deletes events and chat messages past their 3-month retention, daily
  at 03:00 COT. (The sync of Keycloak's own events, D3, is not scheduled yet.)

Each service runs in at most one container (D8) in `us-east` (D16); KRTR_WARM=true at deploy
time keeps one container of each always on (D17). Every function configures logging once when
its container starts (CLAUDE.md). Consumed by `modal deploy` / `modal serve` only.
"""

import logging
import os
from typing import Any

import httpx
import modal

from krtr.back.deploy.config import (
    APP_NAME,
    AUTH_LABEL,
    AUTH_PUBLIC_HOST,
    IMPORT_VOLUME_MOUNT,
    KEYCLOAK_INTERNAL_PORT,
    KEYCLOAK_READY_TIMEOUT_SECONDS,
    REGION,
    WEB_LABEL,
    DeploySecret,
    warm_containers,
)
from krtr.back.deploy.images import build_keycloak_image, build_web_image
from krtr.back.deploy.keycloak_process import start_keycloak, wait_until_ready
from krtr.back.security.credentials.config import IMPORT_VOLUME, VOLUME_IMPORT_DIRECTORY

logger = logging.getLogger(__name__)

WEB_IMAGE = build_web_image()
KEYCLOAK_IMAGE = build_keycloak_image()
WARM_CONTAINERS = warm_containers()
CREDENTIALS_VOLUME = modal.Volume.from_name(IMPORT_VOLUME, create_if_missing=True)
IMPORT_CHUNK_SIZE = 100
IMPORT_PARALLEL_REQUESTS = 8
IMPORT_TIMEOUT_SECONDS = 3 * 60 * 60

app = modal.App(APP_NAME)


def configure_container_logging() -> None:
    """Configures logging once per container, since no CLI entrypoint runs on Modal.

    Returns:
        None.
    """
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )


@app.function(
    image=WEB_IMAGE,
    secrets=[modal.Secret.from_name(DeploySecret.WEB)],
    cpu=0.25,
    memory=512,
    max_containers=1,
    min_containers=WARM_CONTAINERS,
    region=REGION,
    include_source=False,
)
@modal.concurrent(max_inputs=50)
@modal.asgi_app(label=WEB_LABEL)
def web() -> Any:
    """Serves krtr-web: the same app `krtr back web serve` runs, built for production.

    Returns:
        Any: the FastAPI app.
    """
    configure_container_logging()
    from krtr.back.web.app import create_served_app

    return create_served_app()


@app.function(
    image=KEYCLOAK_IMAGE,
    secrets=[modal.Secret.from_name(DeploySecret.AUTH)],
    cpu=1,
    memory=1536,
    max_containers=1,
    min_containers=WARM_CONTAINERS,
    region=REGION,
    startup_timeout=KEYCLOAK_READY_TIMEOUT_SECONDS + 60,
    include_source=False,
)
@modal.concurrent(max_inputs=100)
@modal.asgi_app(label=AUTH_LABEL)
def auth() -> Any:
    """Starts Keycloak, waits until it is ready, and serves it through the gateway (D19).

    Returns:
        Any: the gateway's ASGI app.
    """
    configure_container_logging()
    from krtr.back.security.keycloak.config import GatewayConfig
    from krtr.back.security.keycloak.gateway import build_gateway

    wait_until_ready(start_keycloak())
    return build_gateway(GatewayConfig(public_host=AUTH_PUBLIC_HOST))


@app.function(
    image=KEYCLOAK_IMAGE,
    secrets=[modal.Secret.from_name(DeploySecret.AUTH)],
    volumes={IMPORT_VOLUME_MOUNT.as_posix(): CREDENTIALS_VOLUME},
    cpu=2,
    memory=3072,
    region=REGION,
    timeout=IMPORT_TIMEOUT_SECONDS,
    include_source=False,
)
def auth_import() -> dict[str, int]:
    """Imports the staged users files into the production Keycloak (D20, task 3.5).

    Runs its own Keycloak against the production database (the `auth` function must be stopped)
    and calls the admin API on 127.0.0.1, which the gateway never exposes.

    Returns:
        dict[str, int]: `{"added": ..., "skipped": ...}`.
    """
    configure_container_logging()
    from pathlib import Path

    from krtr.back.security.credentials.importer import import_users, users_files
    from krtr.back.security.keycloak.admin_client import KeycloakAdminClient
    from krtr.back.security.keycloak.config import KeycloakAdminConfig

    CREDENTIALS_VOLUME.reload()
    files = users_files(Path(IMPORT_VOLUME_MOUNT.as_posix()) / VOLUME_IMPORT_DIRECTORY.name)
    process = start_keycloak()
    try:
        wait_until_ready(process)
        config = KeycloakAdminConfig(
            admin_password=os.environ["KC_BOOTSTRAP_ADMIN_PASSWORD"],
            origin=f"http://127.0.0.1:{KEYCLOAK_INTERNAL_PORT}",
        )
        with httpx.Client(timeout=600) as http_client:
            admin = KeycloakAdminClient(config, http_client)
            result = import_users(admin, files, IMPORT_CHUNK_SIZE, IMPORT_PARALLEL_REQUESTS)
    finally:
        process.terminate()
        process.wait(timeout=60)
    return result.model_dump()


@app.function(
    image=WEB_IMAGE,
    secrets=[modal.Secret.from_name(DeploySecret.JOBS)],
    schedule=modal.Cron("0 8 * * *"),  # 03:00 COT.
    cpu=0.125,
    region=REGION,
    include_source=False,
)
def purge_events() -> dict[str, int]:
    """Deletes events and chat messages older than their 3-month retention (G21, §3.6).

    Returns:
        dict[str, int]: how many events and messages were deleted.
    """
    configure_container_logging()
    from krtr.back.ia.messages.store import NeonMessageStore
    from krtr.back.security.audit.retention import purge_expired_events
    from krtr.database.neon.client import NeonClient

    with NeonClient() as client:
        events = purge_expired_events(client)
    messages = NeonMessageStore.from_environment().purge_expired()
    return {"events": events, "messages": messages}
