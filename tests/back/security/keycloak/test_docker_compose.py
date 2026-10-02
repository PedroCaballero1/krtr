"""Tests the local Keycloak's docker-compose.yml: only reachable locally, with no secret inside."""

import re
from pathlib import Path

COMPOSE_FILE = (
    Path(__file__).resolve().parents[4] / "krtr/back/security/keycloak/docker-compose.yml"
)


def test_ports_are_bound_to_localhost_only() -> None:
    """Keycloak and its management port must not be reachable from the local network."""
    ports = re.findall(r'^\s*-\s*"(\S+:\d+:\d+)"', COMPOSE_FILE.read_text(), flags=re.MULTILINE)

    assert ports, "no published ports found"
    assert all(port.startswith("127.0.0.1:") for port in ports)


def test_secrets_come_from_the_environment() -> None:
    """Passwords and the client secret are read from .env, never written in the file."""
    text = COMPOSE_FILE.read_text()
    for variable in (
        "KC_DB_PASSWORD",
        "KC_BOOTSTRAP_ADMIN_PASSWORD",
        "KRTR_WEB_OIDC_CLIENT_SECRET",
    ):
        value = re.search(rf"^\s*{variable}:\s*(\S+)", text, flags=re.MULTILINE).group(1)

        assert value.startswith("${"), variable
