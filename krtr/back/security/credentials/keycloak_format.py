"""Writes passwords and users the way Keycloak 26.8 imports them (task 3.4).

Exists so a password is hashed once, here, with argon2id and the parameters Keycloak itself
uses, and stored as a `password` credential Keycloak verifies without ever seeing the clear
text. The user files follow Keycloak's own export format (`<realm>-users-<n>.json`), which both
`kc.sh import --dir` and the admin `partialImport` accept. Consumed by
`krtr/back/security/credentials/generator.py`.
"""

import base64
import json
import secrets
from typing import Any

from argon2.low_level import ARGON2_VERSION, Type, hash_secret_raw

from krtr.back.security.credentials.config import Argon2Parameters

ARGON2_VERSION_LABEL = "1.3"  # ARGON2_VERSION (0x13), as Keycloak writes it.
PASSWORD_CREDENTIAL_TYPE = "password"
ARGON2_ALGORITHM = "argon2"


def password_credential(
    password: str, parameters: Argon2Parameters, salt: bytes | None = None
) -> dict[str, Any]:
    """Hashes a password into a Keycloak `password` credential.

    Args:
        password: The password in clear; never stored.
        parameters: The argon2id cost.
        salt: The salt; a fresh random one by default (tests pass a fixed one).

    Returns:
        dict[str, Any]: the credential, with `secretData` (hash and salt, base64) and
        `credentialData` (algorithm and cost) as the JSON strings Keycloak expects.
    """
    salt_bytes = salt if salt is not None else secrets.token_bytes(parameters.salt_bytes)
    digest = hash_secret_raw(
        secret=password.encode("utf-8"),
        salt=salt_bytes,
        time_cost=parameters.iterations,
        memory_cost=parameters.memory_kib,
        parallelism=parameters.parallelism,
        hash_len=parameters.hash_length,
        type=Type.ID,
        version=ARGON2_VERSION,
    )
    secret_data = {"value": _b64(digest), "salt": _b64(salt_bytes), "additionalParameters": {}}
    return {
        "type": PASSWORD_CREDENTIAL_TYPE,
        "secretData": json.dumps(secret_data),
        "credentialData": json.dumps(_credential_data(parameters)),
    }


def user_representation(customer_id: str, credential: dict[str, Any]) -> dict[str, Any]:
    """Builds the Keycloak user for one customer: the customer_id is the username (G6).

    No email or names are imported (D5).

    Args:
        customer_id: The customer's ID, e.g. CLI-G4X2AMVD62NR.
        credential: The customer's password credential.

    Returns:
        dict[str, Any]: the user representation.
    """
    return {"username": customer_id, "enabled": True, "credentials": [credential]}


def users_file(realm: str, users: list[dict[str, Any]]) -> dict[str, Any]:
    """Wraps users in the body of a `<realm>-users-<n>.json` file.

    Args:
        realm: The realm they belong to.
        users: The user representations.

    Returns:
        dict[str, Any]: `{"realm": realm, "users": users}`.
    """
    return {"realm": realm, "users": users}


def _credential_data(parameters: Argon2Parameters) -> dict[str, Any]:
    """Describes the hash so Keycloak can verify it with the same cost.

    Args:
        parameters: The argon2id cost.

    Returns:
        dict[str, Any]: Keycloak's `credentialData` for an argon2 password.
    """
    return {
        "hashIterations": parameters.iterations,
        "algorithm": ARGON2_ALGORITHM,
        "additionalParameters": {
            "hashLength": [str(parameters.hash_length)],
            "memory": [str(parameters.memory_kib)],
            "type": ["id"],
            "version": [ARGON2_VERSION_LABEL],
            "parallelism": [str(parameters.parallelism)],
        },
    }


def _b64(raw: bytes) -> str:
    """Encodes bytes as standard base64 text, as Keycloak stores hashes and salts.

    Args:
        raw: The bytes.

    Returns:
        str: their base64 encoding.
    """
    return base64.b64encode(raw).decode("ascii")
