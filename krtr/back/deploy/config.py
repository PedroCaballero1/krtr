"""Defines the configuration of the krtr-web Modal app: names, URLs, images and Keycloak.

Exists so the app's names and public URLs (D11, D21), the Keycloak version and options, and the
demo-mode switch (D17) are declared once, with the reason for each. Consumed by
`krtr/back/deploy/`.
"""

import os
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


APP_NAME = "krtr-web"  # D21.
WORKSPACE = "juan-alvarezo-2002"  # D11.
WEB_LABEL = "krtr"
AUTH_LABEL = "krtr-auth"
WEB_PUBLIC_URL = f"https://{WORKSPACE}--{WEB_LABEL}.modal.run"
AUTH_PUBLIC_HOST = f"{WORKSPACE}--{AUTH_LABEL}.modal.run"
AUTH_PUBLIC_URL = f"https://{AUTH_PUBLIC_HOST}"
REGION = "us-east"  # D16: next to Neon (us-east-2).

FRONTEND_DIST = "krtr/front/dist"
FRONTEND_CONTAINER_DIR = "/app/frontend"
REALM_FILE = "krtr/back/security/keycloak/realm-krtr.json"
KEYCLOAK_IMPORT_DIR = KEYCLOAK_HOME / "data" / "import"
LOGIN_THEME_DIR = "krtr/back/security/keycloak/themes/krtr"  # Task 3.3; the realm's loginTheme.
KEYCLOAK_THEME_DIR = KEYCLOAK_HOME / "themes" / "krtr"
IMPORT_VOLUME_MOUNT = PurePosixPath("/credentials")

# The IA models (MiniLM embeddings and the int4 Qwen LLM) live on a Volume, prepared once by
# the `prepare_models` function, so the web image stays small and starts without downloads.
MODELS_VOLUME = "krtr-models"
MODELS_MOUNT = PurePosixPath("/models")
QWEN_SOURCE = "Qwen/Qwen2.5-1.5B-Instruct"

# The models the chat runs in production (KRTR_IA_* of krtr/back/ia/config.py).
WEB_IA_ENVIRONMENT = {
    "KRTR_IA_EMBEDDING_MODEL": "multilingual_minilm",
    "KRTR_IA_LANGUAGE_MODEL": "py3langid",
    "KRTR_IA_LLM_MODEL": "qwen2_5_1_5b_instruct",
    "KRTR_IA_MODEL_CACHE": MODELS_MOUNT.as_posix(),
}

# Only for the one-off conversion of Qwen to int4 ONNX (README > Conversation agent > LLM);
# torch is a build tool here, never a dependency of the app.
MODEL_BUILD_PACKAGES = (
    "onnxruntime-genai==0.15.2",
    "onnx",
    "onnx-ir",
    "transformers",
    "huggingface_hub",
)
TORCH_CPU_INDEX = "https://download.pytorch.org/whl/cpu"

KEYCLOAK_INTERNAL_PORT = 8081  # The gateway (task 3.7) forwards here.
KEYCLOAK_MANAGEMENT_READY_URL = "http://127.0.0.1:9000/health/ready"
KEYCLOAK_READY_TIMEOUT_SECONDS = 900  # The first start against production runs 237 migrations.

# The Python packages the Keycloak image needs for the gateway and the import, pinned as in
# uv.lock (the image has no uv project, only the krtr sources).
KEYCLOAK_IMAGE_PACKAGES = (
    "fastapi==0.142.2",
    "httpx==0.28.1",
    "pydantic==2.13.5",
    "python-dotenv==1.2.3",
)


class DeploySecret(StrEnum):
    """The Modal secrets of the krtr-web app (task 6.1)."""

    WEB = "krtr-web"  # The FastAPI app.
    AUTH = "krtr-auth"  # Keycloak and the user import.
    JOBS = "krtr-jobs"  # The daily purge and the Keycloak event sync.


class WarmEnvironmentVariable(StrEnum):
    """The deploy-time switch of the demo mode (D17)."""

    WARM = "KRTR_WARM"  # "true" keeps one container of each service always on.


def warm_containers() -> int:
    """Returns `min_containers` for the services, from KRTR_WARM at deploy time (D17).

    Returns:
        int: 1 in demo mode (KRTR_WARM=true), 0 otherwise.
    """
    return 1 if os.environ.get(WarmEnvironmentVariable.WARM, "").lower() == "true" else 0


def keycloak_runtime_environment() -> dict[str, str]:
    """Returns Keycloak's non-secret runtime options (task 3.1): behind the gateway, on loopback.

    Returns:
        dict[str, str]: the KC_* variables for `kc.sh start --optimized`.
    """
    return {
        "KC_HOSTNAME": AUTH_PUBLIC_URL,
        "KC_HTTP_ENABLED": "true",
        "KC_HTTP_HOST": "127.0.0.1",
        "KC_HTTP_PORT": str(KEYCLOAK_INTERNAL_PORT),
        "KC_PROXY_HEADERS": "xforwarded",
        "KC_CACHE": "local",
    }
