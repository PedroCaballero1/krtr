"""Tests waiting for Keycloak: proceed when ready, fail fast if it dies or never gets ready."""

import pytest

from krtr.back.deploy.config import keycloak_runtime_environment
from krtr.back.deploy.keycloak_process import KeycloakDidNotStart, wait_until_ready


class FakeProcess:
    """Stands in for the Keycloak process: alive until told it exited."""

    def __init__(self, exit_code: int | None = None) -> None:
        """Starts alive, or already exited with `exit_code`."""
        self.returncode = exit_code
        self.terminated = False

    def poll(self) -> int | None:
        """Returns the exit code, or None while running."""
        return self.returncode

    def terminate(self) -> None:
        """Records the termination."""
        self.terminated = True


def test_it_returns_once_keycloak_is_ready() -> None:
    """The gateway is only served after /health/ready answers."""
    answers = iter([False, False, True])

    wait_until_ready(
        FakeProcess(), timeout_seconds=60, probe=lambda: next(answers), sleep=lambda _: None
    )


def test_a_keycloak_that_exits_fails_at_once() -> None:
    """A bad database password must not leave the container waiting for 15 minutes."""
    with pytest.raises(KeycloakDidNotStart, match="code 1"):
        wait_until_ready(FakeProcess(exit_code=1), probe=lambda: False, sleep=lambda _: None)


def test_a_keycloak_that_never_gets_ready_is_stopped() -> None:
    """After the timeout, Keycloak is terminated and the start fails."""
    process = FakeProcess()

    with pytest.raises(KeycloakDidNotStart, match="not ready"):
        wait_until_ready(process, timeout_seconds=0, probe=lambda: False, sleep=lambda _: None)

    assert process.terminated


def test_keycloak_listens_only_on_loopback_behind_the_gateway() -> None:
    """D19: only the gateway is exposed; Keycloak trusts its X-Forwarded headers."""
    environment = keycloak_runtime_environment()

    assert environment["KC_HTTP_HOST"] == "127.0.0.1"
    assert environment["KC_PROXY_HEADERS"] == "xforwarded"
    assert environment["KC_HOSTNAME"] == "https://juan-alvarezo-2002--krtr-auth.modal.run"
