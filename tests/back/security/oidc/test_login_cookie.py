"""Tests LoginCookieCodec: the login cookie is unreadable, unforgeable and expires."""

import base64
import os

import pytest

from krtr.back.security.crypto.cipher import AesGcmCipher
from krtr.back.security.oidc.artifacts import InterfaceLanguage, LoginState
from krtr.back.security.oidc.errors import LoginError, LoginFailureReason
from krtr.back.security.oidc.login_cookie import LoginCookieCodec
from tests.back.security.oidc.fakes import START

KEY = os.urandom(32)
LOGIN = LoginState(
    state="the-state",
    nonce="the-nonce",
    code_verifier="the-code-verifier",
    language=InterfaceLanguage.PORTUGUESE,
    expires_at=START.replace(minute=10),
)


def decode_error(value: str | None, codec: LoginCookieCodec | None = None) -> LoginFailureReason:
    """Decodes a value that must be rejected and returns why."""
    with pytest.raises(LoginError) as raised:
        (codec or LoginCookieCodec(AesGcmCipher(KEY))).decode(value, START)
    return raised.value.reason


def test_the_login_survives_the_round_trip_to_keycloak() -> None:
    """What /auth/login stores is exactly what /auth/callback reads back."""
    codec = LoginCookieCodec(AesGcmCipher(KEY))

    assert codec.decode(codec.encode(LOGIN), START) == LOGIN


def test_the_cookie_does_not_reveal_the_nonce_or_the_verifier() -> None:
    """The PKCE verifier is a secret: the browser holds it but must not be able to read it."""
    raw = base64.urlsafe_b64decode(LoginCookieCodec(AesGcmCipher(KEY)).encode(LOGIN))

    assert b"the-code-verifier" not in raw and b"the-nonce" not in raw


def test_a_tampered_cookie_is_rejected() -> None:
    """Flipping one byte must fail AES-GCM's authentication."""
    raw = bytearray(base64.urlsafe_b64decode(LoginCookieCodec(AesGcmCipher(KEY)).encode(LOGIN)))
    raw[-1] ^= 1

    assert (
        decode_error(base64.urlsafe_b64encode(bytes(raw)).decode())
        == LoginFailureReason.INVALID_LOGIN_COOKIE
    )


def test_a_cookie_made_with_another_key_is_rejected() -> None:
    """A cookie forged with any other key must not be accepted."""
    forged = LoginCookieCodec(AesGcmCipher(os.urandom(32))).encode(LOGIN)

    assert decode_error(forged) == LoginFailureReason.INVALID_LOGIN_COOKIE


@pytest.mark.parametrize("value", ["not base64 !!!", "c2hvcnQ"], ids=["not-base64", "too-short"])
def test_garbage_is_rejected_as_invalid(value: str) -> None:
    """Any value that is not one of our cookies is a forged cookie, not a server error."""
    assert decode_error(value) == LoginFailureReason.INVALID_LOGIN_COOKIE


def test_a_missing_cookie_is_reported_as_missing() -> None:
    """A callback without a login in this browser (or after 10 minutes) has no cookie."""
    assert decode_error(None) == LoginFailureReason.MISSING_LOGIN_COOKIE


def test_a_login_older_than_10_minutes_is_rejected() -> None:
    """The login cookie is only good for the 10 minutes /auth/login gives it."""
    codec = LoginCookieCodec(AesGcmCipher(KEY))
    value = codec.encode(LOGIN)

    with pytest.raises(LoginError) as raised:
        codec.decode(value, LOGIN.expires_at)

    assert raised.value.reason == LoginFailureReason.EXPIRED_LOGIN
