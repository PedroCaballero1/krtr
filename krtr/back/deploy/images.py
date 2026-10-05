"""Builds the container images of the krtr-web Modal app.

Exists so each function's image is declared once (D21). The Keycloak image starts from the
official one and runs `kc.sh build`, so `kc.sh start --optimized` skips the build when a
container starts. The realm (task 3.2) and the login theme (task 3.3) are added to it once
they exist. Importing this module requires `modal`: only `modal deploy` / `modal serve` and
Modal containers load it (CLAUDE.md). Consumed by `krtr/back/deploy/app.py` (tasks 6.3, 6.4).
"""

import modal

from krtr.back.deploy.config import KEYCLOAK_HOME, KeycloakImageConfig
from krtr.compute.modal.config import CONTAINER_PYTHON_VERSION


def build_keycloak_image(config: KeycloakImageConfig | None = None) -> modal.Image:
    """Builds the Keycloak image definition, with the build options baked in.

    Exists so the `auth` and `auth_import` functions share one image. Python is added because
    Modal's runtime, and later the gateway of task 3.7, run in this container. The official
    image's `kc.sh` entrypoint is cleared, since Modal starts its own process.

    Args:
        config: The image reference and build options; the defaults when None.

    Returns:
        modal.Image: the image definition, which Modal builds the first time it is used.
    """
    resolved_config = config or KeycloakImageConfig()
    return (
        modal.Image.from_registry(
            resolved_config.image_reference, add_python=CONTAINER_PYTHON_VERSION
        )
        .entrypoint([])
        .run_commands(build_keycloak_command(resolved_config))
    )


def build_keycloak_command(config: KeycloakImageConfig) -> str:
    """Builds the `kc.sh build` command line for the given configuration.

    Exists apart from the image so the exact options baked into Keycloak can be checked
    without building anything.

    Args:
        config: The build options to bake in.

    Returns:
        str: the shell command that runs `kc.sh build` with those options.
    """
    health_enabled = str(config.health_enabled).lower()
    return (
        f"{KEYCLOAK_HOME / 'bin' / 'kc.sh'} build"
        f" --db={config.database_vendor.value} --health-enabled={health_enabled}"
    )
