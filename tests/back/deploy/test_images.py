"""Tests the `kc.sh build` command baked into the Keycloak image; skipped without `modal`."""

import pytest

pytest.importorskip("modal")

from krtr.back.deploy.config import KeycloakImageConfig  # noqa: E402
from krtr.back.deploy.images import build_keycloak_command  # noqa: E402


def test_build_command_bakes_postgres_and_health_into_keycloak() -> None:
    """`kc.sh start --optimized` (task 6.3) needs Postgres and /health/ready already built in."""
    assert build_keycloak_command(KeycloakImageConfig()) == (
        "/opt/keycloak/bin/kc.sh build --db=postgres --health-enabled=true"
    )


def test_build_command_follows_the_health_setting() -> None:
    """Turning health off must reach kc.sh instead of being silently ignored."""
    command = build_keycloak_command(KeycloakImageConfig(health_enabled=False))

    assert command.endswith("--health-enabled=false")
