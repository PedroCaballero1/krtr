"""Tests the Keycloak image configuration: one pinned release, shared with the local Keycloak."""

import json
import re
from pathlib import Path

from krtr.back.deploy.config import (
    KEYCLOAK_HOME,
    KEYCLOAK_IMAGE_REFERENCE,
    KEYCLOAK_THEME_DIR,
    LOGIN_THEME_DIR,
    REALM_FILE,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
LOCAL_COMPOSE_FILE = REPOSITORY_ROOT / "krtr/back/security/keycloak/docker-compose.yml"


def test_keycloak_image_is_pinned_to_an_exact_release() -> None:
    """A floating tag (latest, 26) would swap Keycloak under the deployed realm without notice."""
    assert re.fullmatch(r"quay\.io/keycloak/keycloak:\d+\.\d+\.\d+", KEYCLOAK_IMAGE_REFERENCE)


def test_modal_and_local_keycloak_run_the_same_release() -> None:
    """The realm and theme are tried locally first, so Modal must run that exact Keycloak."""
    compose_text = LOCAL_COMPOSE_FILE.read_text()
    compose_images = re.findall(r"^\s*image:\s*(\S+)", compose_text, flags=re.MULTILINE)

    assert compose_images == [KEYCLOAK_IMAGE_REFERENCE]


def test_modal_image_ships_the_theme_the_realm_selects() -> None:
    """Keycloak looks the realm's loginTheme up by folder name under /opt/keycloak/themes."""
    realm = json.loads((REPOSITORY_ROOT / REALM_FILE).read_text(encoding="utf-8"))
    theme_source = REPOSITORY_ROOT / LOGIN_THEME_DIR

    assert KEYCLOAK_THEME_DIR == KEYCLOAK_HOME / "themes" / realm["loginTheme"]
    assert theme_source.name == realm["loginTheme"]
    assert (theme_source / "login" / "theme.properties").is_file()
