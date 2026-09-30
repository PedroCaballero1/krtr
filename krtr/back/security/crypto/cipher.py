"""Implements AES-256-GCM encryption for at-rest-only, opaque columns.

Exists so `events.properties` and `app_sessions.tokens_ciphertext` (§3.5 and
D1 of docs/guia-web-seguridad.md) are encrypted the same way, through one
small, reusable class, instead of each caller handling nonces and AEAD
tags itself. Consumed by `krtr/back/security/audit/recorder.py` and
`krtr/back/security/sessions/`.
"""

import logging
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)

NONCE_LENGTH_BYTES = 12  # Standard AES-GCM nonce size.


class AesGcmCipher:
    """Encrypts and decrypts bytes with AES-256-GCM.

    Exists to store a single, self-contained blob (nonce + ciphertext, per
    §3.5: "cifrado con AES-256-GCM (nonce + ciphertext)") instead of
    managing the nonce as a separate column. Consumed by any code writing
    or reading an encrypted `BYTEA` column.
    """

    def __init__(self, key: bytes) -> None:
        """Builds a cipher bound to one AES-256 key.

        Args:
            key: The raw 32-byte AES-256 key (see `CryptoConfig.decoded_key`).
        """
        self._aesgcm = AESGCM(key)

    def encrypt(self, plaintext: bytes) -> bytes:
        """Encrypts plaintext with a fresh random nonce.

        Exists so every encryption uses its own nonce (required for AES-GCM's
        security guarantees) without the caller managing it.

        Args:
            plaintext: The bytes to encrypt.

        Returns:
            bytes: the random nonce concatenated with the ciphertext
            (including its authentication tag).
        """
        nonce = os.urandom(NONCE_LENGTH_BYTES)
        ciphertext = self._aesgcm.encrypt(nonce, plaintext, None)
        return nonce + ciphertext

    def decrypt(self, nonce_and_ciphertext: bytes) -> bytes:
        """Decrypts a nonce + ciphertext blob produced by `encrypt`.

        Args:
            nonce_and_ciphertext: The stored blob: the nonce followed by the
                ciphertext and its authentication tag.

        Returns:
            bytes: the original plaintext.

        Raises:
            ValueError: if the blob is too short to contain a nonce.
            cryptography.exceptions.InvalidTag: if the ciphertext was
                tampered with or the wrong key is used.
        """
        if len(nonce_and_ciphertext) < NONCE_LENGTH_BYTES:
            raise ValueError("Ciphertext is too short to contain a nonce")
        nonce = nonce_and_ciphertext[:NONCE_LENGTH_BYTES]
        ciphertext = nonce_and_ciphertext[NONCE_LENGTH_BYTES:]
        return self._aesgcm.decrypt(nonce, ciphertext, None)
