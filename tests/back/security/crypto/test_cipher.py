"""Tests AesGcmCipher: the round trip, opacity, and tamper detection."""

import os

import pytest
from cryptography.exceptions import InvalidTag

from krtr.back.security.crypto.cipher import AesGcmCipher

KEY = os.urandom(32)


def test_decrypt_recovers_the_original_plaintext() -> None:
    """The whole point of the cipher: what comes out must equal what went in."""
    cipher = AesGcmCipher(KEY)
    plaintext = b'{"customer_id": "12345", "path": "/api/chat/messages"}'

    ciphertext = cipher.encrypt(plaintext)

    assert cipher.decrypt(ciphertext) == plaintext


def test_ciphertext_is_not_the_plaintext_and_not_readable_json() -> None:
    """Guards the "properties cifrado, no legible" requirement (§3.5)."""
    cipher = AesGcmCipher(KEY)
    plaintext = b'{"customer_id": "12345"}'

    ciphertext = cipher.encrypt(plaintext)

    assert ciphertext != plaintext
    assert b"customer_id" not in ciphertext
    with pytest.raises(UnicodeDecodeError):
        ciphertext.decode("utf-8")


def test_each_encryption_uses_a_fresh_nonce() -> None:
    """Encrypting the same plaintext twice must never produce the same blob."""
    cipher = AesGcmCipher(KEY)
    plaintext = b"same plaintext"

    assert cipher.encrypt(plaintext) != cipher.encrypt(plaintext)


def test_tampering_with_the_ciphertext_fails_authentication() -> None:
    """A single flipped byte must be detected, not silently decrypted wrong."""
    cipher = AesGcmCipher(KEY)
    ciphertext = bytearray(cipher.encrypt(b"original"))
    ciphertext[-1] ^= 0xFF

    with pytest.raises(InvalidTag):
        cipher.decrypt(bytes(ciphertext))


def test_decrypting_with_the_wrong_key_fails() -> None:
    """A different key must never be able to read another key's data."""
    ciphertext = AesGcmCipher(KEY).encrypt(b"secret")
    other_cipher = AesGcmCipher(os.urandom(32))

    with pytest.raises(InvalidTag):
        other_cipher.decrypt(ciphertext)


def test_decrypt_rejects_a_blob_too_short_to_contain_a_nonce() -> None:
    """Guards against a truncated/corrupt stored value crashing with a confusing error."""
    cipher = AesGcmCipher(KEY)

    with pytest.raises(ValueError, match="too short"):
        cipher.decrypt(b"short")
