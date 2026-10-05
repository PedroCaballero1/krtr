"""Tests CryptoConfig's key validation and environment loading."""

import base64

import pytest

from krtr.back.security.crypto.config import (
    AES_256_KEY_LENGTH_BYTES,
    CryptoConfig,
    CryptoEnvironmentVariable,
)

VALID_KEY_B64 = base64.b64encode(b"0" * 32).decode("ascii")


def test_valid_32_byte_key_decodes_back_to_the_original_bytes() -> None:
    """The round trip a real caller relies on: config in, raw key out."""
    config = CryptoConfig(key=VALID_KEY_B64)

    assert config.decoded_key() == b"0" * 32
    assert len(config.decoded_key()) == AES_256_KEY_LENGTH_BYTES


def test_a_key_of_the_wrong_length_is_rejected() -> None:
    """A 16-byte (AES-128) key must not silently pass as AES-256."""
    short_key_b64 = base64.b64encode(b"short-key").decode("ascii")

    with pytest.raises(ValueError, match="32 bytes"):
        CryptoConfig(key=short_key_b64)


def test_a_non_base64_key_is_rejected() -> None:
    """An operator pasting a raw (non-base64) key must get a clear error."""
    with pytest.raises(ValueError, match="base64"):
        CryptoConfig(key="not-valid-base64!!!")


def test_from_environment_reads_the_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies KRTR_EVENTS_KEY is read and validated."""
    monkeypatch.setenv(CryptoEnvironmentVariable.EVENTS_KEY, VALID_KEY_B64)

    config = CryptoConfig.from_environment()

    assert config.decoded_key() == b"0" * 32


def test_from_environment_raises_when_the_key_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing encryption key must fail fast, not fall back to a default."""
    monkeypatch.delenv(CryptoEnvironmentVariable.EVENTS_KEY, raising=False)

    with pytest.raises(ValueError, match="Missing required environment variable"):
        CryptoConfig.from_environment()


def test_from_environment_reads_the_tokens_key_apart_from_the_events_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The OIDC tokens get their own key, so leaking one key never exposes both kinds of data."""
    tokens_key = base64.b64encode(b"1" * 32).decode("ascii")
    monkeypatch.setenv(CryptoEnvironmentVariable.EVENTS_KEY, VALID_KEY_B64)
    monkeypatch.setenv(CryptoEnvironmentVariable.TOKENS_KEY, tokens_key)

    config = CryptoConfig.from_environment(CryptoEnvironmentVariable.TOKENS_KEY)

    assert config.decoded_key() == b"1" * 32


def test_a_missing_tokens_key_names_its_own_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    """The error must say which key is missing, so the operator fixes the right secret."""
    monkeypatch.delenv(CryptoEnvironmentVariable.TOKENS_KEY, raising=False)

    with pytest.raises(ValueError, match=CryptoEnvironmentVariable.TOKENS_KEY.value):
        CryptoConfig.from_environment(CryptoEnvironmentVariable.TOKENS_KEY)
