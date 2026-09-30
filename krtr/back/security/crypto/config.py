"""Defines configuration for the AES-256-GCM encryption used across krtr-web.

Exists so the encryption key — shared by the `events.properties` and
`app_sessions.tokens_ciphertext` columns — is read and validated from the
environment (or, in production, Secret Manager injected as an env var, per
§6.2 of docs/guia-web-seguridad.md) in exactly one place. Consumed by
`krtr/back/security/crypto/cipher.py`.
"""

import base64
import binascii
import logging
import os
from enum import StrEnum

from pydantic import BaseModel, SecretStr, field_validator

logger = logging.getLogger(__name__)

AES_256_KEY_LENGTH_BYTES = 32


class CryptoEnvironmentVariable(StrEnum):
    """The environment variable `CryptoConfig` reads the encryption key from.

    Centralizes the variable name so the config loader, the README and the
    tests never disagree on spelling. Consumed by `CryptoConfig.from_environment`.
    """

    EVENTS_KEY = "KRTR_EVENTS_KEY"  # Base64-encoded 32-byte AES-256 key.


class CryptoConfig(BaseModel):
    """Configuration for AES-256-GCM encryption.

    Exists to give `AesGcmCipher` a validated 32-byte key instead of a raw,
    unchecked environment string. Consumed by
    `krtr/back/security/crypto/cipher.py`.
    """

    key: SecretStr  # Base64-encoded; decodes to exactly AES_256_KEY_LENGTH_BYTES.

    @field_validator("key")
    @classmethod
    def _validate_key_decodes_to_32_bytes(cls, value: SecretStr) -> SecretStr:
        """Ensures the key is valid base64 that decodes to a 32-byte AES-256 key.

        Args:
            value: The base64-encoded key, as given by the caller or the environment.

        Returns:
            SecretStr: the same value, unchanged, once validated.

        Raises:
            ValueError: if the value is not valid base64, or does not decode
                to exactly 32 bytes.
        """
        try:
            decoded = base64.b64decode(value.get_secret_value(), validate=True)
        except binascii.Error as error:
            raise ValueError(f"Encryption key is not valid base64: {error}") from error
        if len(decoded) != AES_256_KEY_LENGTH_BYTES:
            raise ValueError(
                f"Encryption key must decode to {AES_256_KEY_LENGTH_BYTES} bytes, "
                f"got {len(decoded)}"
            )
        return value

    def decoded_key(self) -> bytes:
        """Returns the raw 32-byte AES-256 key.

        Returns:
            bytes: the decoded key, ready for `AesGcmCipher`.
        """
        return base64.b64decode(self.key.get_secret_value())

    @classmethod
    def from_environment(cls) -> "CryptoConfig":
        """Builds a CryptoConfig from `KRTR_EVENTS_KEY`.

        Args:
            None.

        Returns:
            CryptoConfig: the validated configuration.

        Raises:
            ValueError: if the environment variable is missing, empty, or
                not a valid 32-byte base64-encoded key.
        """
        key = os.environ.get(CryptoEnvironmentVariable.EVENTS_KEY)
        if not key:
            raise ValueError(
                "Missing required environment variable: "
                f"{CryptoEnvironmentVariable.EVENTS_KEY.value}"
            )
        logger.debug("Loaded encryption key from the environment")
        return cls(key=key)
