"""Tests the Keycloak credential format: an argon2id hash Keycloak verifies, never the password."""

import base64
import json

from argon2.low_level import ARGON2_VERSION, Type, hash_secret_raw

from krtr.back.security.credentials.config import Argon2Parameters
from krtr.back.security.credentials.keycloak_format import (
    password_credential,
    user_representation,
    users_file,
)

PARAMETERS = Argon2Parameters()


def recompute(password: str, salt: bytes, parameters: Argon2Parameters = PARAMETERS) -> str:
    """Hashes a password the way Keycloak verifies one, from the stored cost."""
    digest = hash_secret_raw(
        password.encode(),
        salt,
        time_cost=parameters.iterations,
        memory_cost=parameters.memory_kib,
        parallelism=parameters.parallelism,
        hash_len=parameters.hash_length,
        type=Type.ID,
        version=ARGON2_VERSION,
    )
    return base64.b64encode(digest).decode()


def test_the_stored_hash_verifies_the_password_and_nothing_else() -> None:
    """Keycloak recomputes argon2id with the stored salt; only the right password matches."""
    credential = password_credential("Ab3dE6gH", PARAMETERS)
    secret = json.loads(credential["secretData"])
    salt = base64.b64decode(secret["salt"])

    assert secret["value"] == recompute("Ab3dE6gH", salt)
    assert secret["value"] != recompute("Ab3dE6gh", salt)
    assert "Ab3dE6gH" not in json.dumps(credential)


def test_the_cost_is_what_keycloak_26_writes() -> None:
    """Keycloak reads algorithm and cost from credentialData; they must match its own defaults."""
    data = json.loads(password_credential("x", PARAMETERS)["credentialData"])

    assert data == {
        "hashIterations": 5,
        "algorithm": "argon2",
        "additionalParameters": {
            "hashLength": ["32"],
            "memory": ["7168"],
            "type": ["id"],
            "version": ["1.3"],
            "parallelism": ["1"],
        },
    }


def test_every_credential_gets_its_own_salt() -> None:
    """Two customers with the same password must not share a hash."""
    first = json.loads(password_credential("same", PARAMETERS)["secretData"])
    second = json.loads(password_credential("same", PARAMETERS)["secretData"])

    assert first["salt"] != second["salt"]
    assert first["value"] != second["value"]
    assert len(base64.b64decode(first["salt"])) == 16


def test_a_user_is_the_customer_id_with_one_password_and_no_personal_data() -> None:
    """D5: no email or names are imported; the username is the customer_id (G6)."""
    credential = password_credential("x", PARAMETERS)

    user = user_representation("CLI-G4X2AMVD62NR", credential)

    assert user == {"username": "CLI-G4X2AMVD62NR", "enabled": True, "credentials": [credential]}
    assert users_file("krtr", [user]) == {"realm": "krtr", "users": [user]}
