"""Defines the configuration of the krtr-web Modal app's images.

Exists so the Keycloak version and the options baked into its image are declared once, with
the reason for each, instead of inline in the image definition. Consumed by
`krtr/back/deploy/images.py`.
"""

from enum import StrEnum
from pathlib import PurePosixPath

from pydantic import BaseModel

# Same tag as krtr/back/security/keycloak/docker-compose.yml, so local and Modal run one version.
KEYCLOAK_IMAGE_REFERENCE = "quay.io/keycloak/keycloak:26.8.0"

# Where the official image installs Keycloak.
KEYCLOAK_HOME = PurePosixPath("/opt/keycloak")


class KeycloakDatabaseVendor(StrEnum):
    """The database vendor `kc.sh build --db` bakes into the Keycloak image.

    Exists because Keycloak fixes its vendor at build time; krtr only uses Postgres (Neon).
    Consumed by `KeycloakImageConfig`.
    """

    POSTGRES = "postgres"


class KeycloakImageConfig(BaseModel):
    """Configuration of the Keycloak image used by the `auth` and `auth_import` functions.

    Exists so the app and its tests read the same image reference and build options. Only
    build-time options belong here: `kc.sh build` bakes them into the image, so
    `kc.sh start --optimized` (task 6.3) skips that step when a container starts. Runtime
    options (hostname, ports, cache, database URL) are set when the function starts.
    Consumed by `krtr/back/deploy/images.py`.
    """

    image_reference: str = KEYCLOAK_IMAGE_REFERENCE
    database_vendor: KeycloakDatabaseVendor = KeycloakDatabaseVendor.POSTGRES
    health_enabled: bool = True  # Serves /health/ready, which task 6.3 waits on at startup.
