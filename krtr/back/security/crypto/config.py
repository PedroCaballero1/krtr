"""Defines configuration for the AES-256-GCM encryption used across krtr-web.

Exists so each encryption key — one for `events.properties`, another for the
OIDC tokens in `app_sessions.tokens_ciphertext` and the login cookie — is read
and validated from the environment (in production, Modal injects them from the
`krtr-web` secret, per task 6.1 of docs/guia-web-seguridad_modal.md) in exactly
one place. Consumed by `krtr/back/security/crypto/cipher.py`.
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
    """The environment variables `CryptoConfig` reads an encryption key from.

    Centralizes the variable names so the config loader, the README and the
    tests never disagree on spelling. Each purpose gets its own key, so one
    leaking does not expose the other's data. Consumed by
    `CryptoConfig.from_environment`.
    """

    EVENTS_KEY = "KRTR_EVENTS_KEY"  # Base64-encoded 32-byte AES-256 key for events.
    TOKENS_KEY = "KRTR_TOKENS_KEY"  # Same format; OIDC tokens and the login cookie.


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
    def from_environment(
        cls, variable: CryptoEnvironmentVariable = CryptoEnvironmentVariable.EVENTS_KEY
    ) -> "CryptoConfig":
        """Builds a CryptoConfig from one of the key environment variables.

        Args:
            variable: Which key to read; the events key unless told otherwise.

        Returns:
            CryptoConfig: the validated configuration.

        Raises:
            ValueError: if the environment variable is missing, empty, or
                not a valid 32-byte base64-encoded key.
        """
        key = os.environ.get(variable)
        if not key:
            raise ValueError(f"Missing required environment variable: {variable.value}")
        logger.debug("Loaded encryption key %s from the environment", variable.value)
        return cls(key=key)
