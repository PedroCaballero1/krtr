"""Builds the container images of the krtr-web Modal app.

Exists so each function's image is declared once (D21, D18):

- the web image installs the locked dependencies without the `dev` group, like
  `krtr/compute/modal/app.py`, and adds the `krtr` sources and the built SPA;
- the Keycloak image starts from the official one and runs `kc.sh build`, so
  `kc.sh start --optimized` skips the build when a container starts, and adds the realm (task
  3.2), the login theme (task 3.3), plus the few Python packages and sources the gateway (task
  3.7) and the import (task 3.5) run with.

Importing this module requires `modal`: only `modal deploy` / `modal serve` and Modal
containers load it (CLAUDE.md). Consumed by `krtr/back/deploy/app.py`.
"""

import modal

from krtr.back.deploy.config import (
    FRONTEND_CONTAINER_DIR,
    FRONTEND_DIST,
    KEYCLOAK_HOME,
    KEYCLOAK_IMAGE_PACKAGES,
    KEYCLOAK_IMPORT_DIR,
    KEYCLOAK_THEME_DIR,
    LOGIN_THEME_DIR,
    MODEL_BUILD_PACKAGES,
    REALM_FILE,
    TORCH_CPU_INDEX,
    WEB_IA_ENVIRONMENT,
    KeycloakImageConfig,
)
from krtr.compute.modal.config import (
    CONTAINER_PYTHON_VERSION,
    IMAGE_SOURCE_IGNORE_PATTERNS,
    REPOSITORY_ROOT,
)


def build_web_image() -> modal.Image:
    """Builds the image of the `web` function and the jobs: the locked app and the SPA.

    Returns:
        modal.Image: the image definition.
    """
    return _with_krtr_sources(_locked_base()).add_local_dir(
        REPOSITORY_ROOT / FRONTEND_DIST, FRONTEND_CONTAINER_DIR
    )


def build_model_builder_image() -> modal.Image:
    """Builds the image of `prepare_models`: the locked app plus the Qwen conversion tools.

    Returns:
        modal.Image: the image definition.
    """
    builder = _locked_base().uv_pip_install("torch", index_url=TORCH_CPU_INDEX)
    return _with_krtr_sources(builder.uv_pip_install(*MODEL_BUILD_PACKAGES))


def _locked_base() -> modal.Image:
    """Builds the shared base: Python, the locked dependencies without `dev`, and the env.

    Build steps (pip, uv) must come before local files, so callers add theirs to this base
    and the sources last.

    Returns:
        modal.Image: the base image definition.
    """
    return (
        modal.Image.debian_slim(python_version=CONTAINER_PYTHON_VERSION)
        .uv_sync(str(REPOSITORY_ROOT), frozen=True, extra_options="--no-dev")
        .env(
            {
                "KRTR_WEB_ENVIRONMENT": "production",
                "KRTR_WEB_FRONTEND_DIST_DIR": FRONTEND_CONTAINER_DIR,
                **WEB_IA_ENVIRONMENT,
            }
        )
    )


def _with_krtr_sources(image: modal.Image) -> modal.Image:
    """Adds the `krtr` package sources, the last step of an image (they are mounted, not built).

    Args:
        image: The image to add them to.

    Returns:
        modal.Image: the image with the sources.
    """
    return image.add_local_python_source("krtr", ignore=list(IMAGE_SOURCE_IGNORE_PATTERNS))


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
        .pip_install(*KEYCLOAK_IMAGE_PACKAGES)
        .add_local_file(
            REPOSITORY_ROOT / REALM_FILE, (KEYCLOAK_IMPORT_DIR / "realm-krtr.json").as_posix()
        )
        .add_local_dir(REPOSITORY_ROOT / LOGIN_THEME_DIR, KEYCLOAK_THEME_DIR.as_posix())
        .add_local_python_source("krtr", ignore=list(IMAGE_SOURCE_IGNORE_PATTERNS))
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
