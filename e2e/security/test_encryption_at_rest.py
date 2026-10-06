"""Checks, in the production database, that event properties and chat texts are encrypted (7.2).

Reads the latest rows of `events.properties` and `messages.content` straight from Neon
(NEON_DB_HOST in .env) and checks they are AES-256-GCM blobs: nonce + ciphertext + tag, a
fresh nonce per row, nothing readable, and decryptable only with the app's key. Failures
report counts, never the stored bytes or the decrypted text.
"""

import json
import os
from enum import StrEnum

import pytest
from cryptography.exceptions import InvalidTag

from krtr.back.security.crypto.cipher import NONCE_LENGTH_BYTES, AesGcmCipher
from krtr.back.security.crypto.config import (
    AES_256_KEY_LENGTH_BYTES,
    CryptoConfig,
    CryptoEnvironmentVariable,
)
from krtr.database.neon.client import NeonClient
from krtr.database.queries import load_sql

SAMPLE_SIZE = 50
GCM_TAG_LENGTH_BYTES = 16
MINIMUM_BLOB_LENGTH = NONCE_LENGTH_BYTES + GCM_TAG_LENGTH_BYTES


class EncryptedColumn(StrEnum):
    """The encrypted columns checked here, as `<table>/<query file>` of krtr/database/queries."""

    EVENT_PROPERTIES = "events/select_latest_properties.sql"
    MESSAGE_CONTENT = "messages/select_latest_content.sql"


COLUMN_KEYS = {
    EncryptedColumn.EVENT_PROPERTIES: CryptoEnvironmentVariable.EVENTS_KEY,
    EncryptedColumn.MESSAGE_CONTENT: CryptoEnvironmentVariable.MESSAGES_KEY,
}


def latest_blobs(database: NeonClient, column: EncryptedColumn) -> list[bytes]:
    """Reads the column's latest stored values, as raw bytes.

    Args:
        database: The production database.
        column: Which encrypted column to read.

    Returns:
        list[bytes]: up to SAMPLE_SIZE stored values, newest first.
    """
    table, query_file = column.value.split("/")
    rows = database.fetch_all(load_sql(table, query_file), {"limit": SAMPLE_SIZE})
    return [bytes(row[0]) for row in rows]


def is_readable(blob: bytes) -> bool:
    """Tells whether the bytes read as UTF-8 text, which AES-GCM output practically never does.

    Args:
        blob: A stored value.

    Returns:
        bool: True if the bytes decode as UTF-8 (JSON included).
    """
    try:
        blob.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def decrypts(cipher: AesGcmCipher, blob: bytes) -> bool:
    """Tells whether the blob authenticates and decrypts under the cipher's key.

    Args:
        cipher: The cipher with the app's key.
        blob: A stored value.

    Returns:
        bool: True if GCM's tag checks out.
    """
    try:
        cipher.decrypt(blob)
    except InvalidTag:
        return False
    return True


def column_cipher(column: EncryptedColumn) -> AesGcmCipher:
    """Builds the cipher for the column's key from .env, or skips the test without it.

    Args:
        column: Which encrypted column.

    Returns:
        AesGcmCipher: the app's cipher for that column.
    """
    try:
        config = CryptoConfig.from_environment(COLUMN_KEYS[column])
    except ValueError as missing:
        pytest.skip(str(missing))
    return AesGcmCipher(config.decoded_key())


@pytest.mark.parametrize("column", list(EncryptedColumn))
def test_stored_values_are_aes_gcm_ciphertext(
    production_database: NeonClient, column: EncryptedColumn
) -> None:
    """3.5/3.6: each value is nonce + ciphertext + tag, with its own nonce, and unreadable."""
    blobs = latest_blobs(production_database, column)
    too_short = sum(len(blob) < MINIMUM_BLOB_LENGTH for blob in blobs)
    readable = sum(is_readable(blob) for blob in blobs)
    distinct_nonces = len({blob[:NONCE_LENGTH_BYTES] for blob in blobs})

    assert blobs, f"No rows to check in {column.value}"
    assert too_short == 0
    assert readable == 0
    assert distinct_nonces == len(blobs)


@pytest.mark.parametrize("column", list(EncryptedColumn))
def test_stored_values_open_only_with_the_app_key(
    production_database: NeonClient, column: EncryptedColumn
) -> None:
    """The app's key authenticates every value; a different key opens none."""
    blobs = latest_blobs(production_database, column)
    app_cipher = column_cipher(column)
    other_cipher = AesGcmCipher(os.urandom(AES_256_KEY_LENGTH_BYTES))

    opened_with_app_key = sum(decrypts(app_cipher, blob) for blob in blobs)
    opened_with_other_key = sum(decrypts(other_cipher, blob) for blob in blobs)

    assert blobs, f"No rows to check in {column.value}"
    assert opened_with_app_key == len(blobs)
    assert opened_with_other_key == 0


def test_event_properties_decrypt_to_json_objects(production_database: NeonClient) -> None:
    """The plaintext behind `events.properties` is the event's JSON (so the check above is real)."""
    blobs = latest_blobs(production_database, EncryptedColumn.EVENT_PROPERTIES)
    cipher = column_cipher(EncryptedColumn.EVENT_PROPERTIES)

    objects = sum(isinstance(json.loads(cipher.decrypt(blob)), dict) for blob in blobs)

    assert objects == len(blobs)
