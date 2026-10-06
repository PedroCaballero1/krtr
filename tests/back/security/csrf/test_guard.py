"""Tests the CSRF checks: only krtr-web's origin, and only a header that echoes the cookie."""

import pytest

from krtr.back.security.csrf.errors import CsrfFailureReason, CsrfRejected
from krtr.back.security.csrf.guard import check_origin, check_token, new_csrf_token

APP = "https://juan-alvarezo-2002--krtr.modal.run"


def origin_error(origin: str | None, referer: str | None = None) -> CsrfFailureReason:
    """Runs the Origin check on a request that must be rejected and returns why."""
    with pytest.raises(CsrfRejected) as raised:
        check_origin(origin, referer, APP)
    return raised.value.reason


def token_error(cookie: str | None, header: str | None) -> CsrfFailureReason:
    """Runs the double-submit check on a request that must be rejected and returns why."""
    with pytest.raises(CsrfRejected) as raised:
        check_token(cookie, header)
    return raised.value.reason


def test_the_apps_own_origin_is_accepted() -> None:
    """The SPA's own requests carry the app's origin and must pass."""
    check_origin(APP, None, APP)


def test_another_modal_app_is_a_foreign_origin() -> None:
    """modal.run is shared, so a sibling app is same-site but must still be rejected."""
    assert origin_error("https://attacker--evil.modal.run") == CsrfFailureReason.FOREIGN_ORIGIN


def test_a_lookalike_host_is_a_foreign_origin() -> None:
    """A prefix match would let `<app>.attacker.com` through; origins must match exactly."""
    lookalike = "https://juan-alvarezo-2002--krtr.modal.run.attacker.com"

    assert origin_error(lookalike) == CsrfFailureReason.FOREIGN_ORIGIN


def test_plain_http_is_a_foreign_origin() -> None:
    """The scheme is part of the origin: an http page cannot act on the https app."""
    assert origin_error("http://juan-alvarezo-2002--krtr.modal.run") == (
        CsrfFailureReason.FOREIGN_ORIGIN
    )


def test_the_referer_counts_when_origin_is_absent() -> None:
    """Some clients omit Origin; the Referer's origin then decides, whatever its path."""
    check_origin(None, f"{APP}/app/support?x=1", APP)

    assert origin_error(None, "https://evil.example/page") == CsrfFailureReason.FOREIGN_ORIGIN


def test_origin_wins_over_a_matching_referer() -> None:
    """A forged-looking Referer must not rescue a request whose Origin is foreign."""
    assert origin_error("https://evil.example", f"{APP}/app") == CsrfFailureReason.FOREIGN_ORIGIN


@pytest.mark.parametrize("origin", [None, "", "null"])
def test_a_request_naming_no_origin_is_rejected(origin: str | None) -> None:
    """No Origin, an empty one, or the opaque `null` (sandboxed iframes) proves nothing."""
    assert origin_error(origin) == CsrfFailureReason.MISSING_ORIGIN


def test_a_header_that_echoes_the_cookie_is_accepted() -> None:
    """The double submit: the SPA copies the cookie into X-KRTR-CSRF."""
    token = new_csrf_token()

    check_token(token, token)


@pytest.mark.parametrize(("cookie", "header"), [(None, "t"), ("t", None), ("", ""), (None, None)])
def test_a_missing_cookie_or_header_is_rejected(cookie: str | None, header: str | None) -> None:
    """A forged form post carries the cookie but cannot add the header (and vice versa)."""
    assert token_error(cookie, header) == CsrfFailureReason.MISSING_TOKEN


def test_a_header_that_does_not_echo_the_cookie_is_rejected() -> None:
    """Another page cannot read the cookie, so any value it guesses must fail."""
    assert token_error(new_csrf_token(), new_csrf_token()) == CsrfFailureReason.TOKEN_MISMATCH


def test_tokens_are_unpredictable_and_cookie_safe() -> None:
    """256 random bits, URL-safe, so they go in a cookie and a header without encoding."""
    tokens = {new_csrf_token() for _ in range(100)}

    assert len(tokens) == 100
    assert all(len(token) >= 43 and token.isascii() and ";" not in token for token in tokens)
