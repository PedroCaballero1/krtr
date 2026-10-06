"""Starts Keycloak inside a Modal container and waits until it is ready (tasks 6.3, 6.4).

Exists because the `auth` and `auth_import` functions both run Keycloak as a child process on
127.0.0.1:8081: `kc.sh start --optimized --import-realm` imports realm-krtr.json on its first
start (and skips it after, IGNORE_EXISTING), and the function only proceeds once
`/health/ready` on the management port answers. Free of `modal`, so it is tested locally.
Consumed by `krtr/back/deploy/app.py`.
"""

import logging
import os
import subprocess
import time
from collections.abc import Callable

import httpx

from krtr.back.deploy.config import (
    KEYCLOAK_HOME,
    KEYCLOAK_MANAGEMENT_READY_URL,
    KEYCLOAK_READY_TIMEOUT_SECONDS,
    keycloak_runtime_environment,
)

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 2.0
START_COMMAND = [str(KEYCLOAK_HOME / "bin" / "kc.sh"), "start", "--optimized", "--import-realm"]


class KeycloakDidNotStart(RuntimeError):
    """Raised when Keycloak exits or is not ready before the timeout."""


def start_keycloak() -> subprocess.Popen[bytes]:
    """Starts Keycloak with its runtime options; the secrets come from the container's env.

    Returns:
        subprocess.Popen[bytes]: the running Keycloak process (its logs go to the container's).
    """
    environment = {**os.environ, **keycloak_runtime_environment()}
    logger.info("Starting Keycloak")
    return subprocess.Popen(START_COMMAND, env=environment)


def wait_until_ready(
    process: subprocess.Popen[bytes],
    timeout_seconds: float = KEYCLOAK_READY_TIMEOUT_SECONDS,
    probe: Callable[[], bool] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Blocks until Keycloak reports ready, failing fast if it exits or takes too long.

    Args:
        process: The Keycloak process.
        timeout_seconds: How long to wait.
        probe: Tells whether Keycloak is ready; `/health/ready` by default.
        sleep: Waits between probes; a fake in tests.

    Returns:
        None.

    Raises:
        KeycloakDidNotStart: if Keycloak exits, or is not ready in time.
    """
    is_ready = probe or _health_ready
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise KeycloakDidNotStart(f"Keycloak exited with code {process.returncode}")
        if is_ready():
            logger.info("Keycloak is ready")
            return
        sleep(POLL_INTERVAL_SECONDS)
    process.terminate()
    raise KeycloakDidNotStart(f"Keycloak was not ready after {timeout_seconds} s")


def _health_ready() -> bool:
    """Asks Keycloak's management port whether it is ready.

    Returns:
        bool: True when `/health/ready` answers 200.
    """
    try:
        return httpx.get(KEYCLOAK_MANAGEMENT_READY_URL, timeout=5).status_code == 200
    except httpx.HTTPError:
        return False
