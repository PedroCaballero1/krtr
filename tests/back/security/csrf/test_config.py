"""Tests CsrfConfig: the allowed origin comes from KRTR_PUBLIC_URL, written as browsers do."""

import pytest

from krtr.back.security.csrf.config import CsrfConfig, origin_of


@pytest.mark.parametrize(
    ("url", "origin"),
    [
        (
            "https://juan-alvarezo-2002--krtr.modal.run",
            "https://juan-alvarezo-2002--krtr.modal.run",
        ),
        ("https://Krtr.Example/app/path?q=1", "https://krtr.example"),
        ("https://krtr.example:443/", "https://krtr.example"),
        ("http://localhost:8000/", "http://localhost:8000"),
        ("http://localhost:80", "http://localhost"),
    ],
)
def test_an_origin_is_scheme_host_and_non_default_port(url: str, origin: str) -> None:
    """Paths, letter case and default ports must not make the same origin look different."""
    assert origin_of(url) == origin


@pytest.mark.parametrize("url", [None, "", "null", "/relative/path", "krtr.example"])
def test_a_value_without_scheme_and_host_has_no_origin(url: str | None) -> None:
    """Values that name no origin must never match the allowed one."""
    assert origin_of(url) is None


def test_the_allowed_origin_follows_krtr_public_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Production sets KRTR_PUBLIC_URL to the Modal URL; the check must follow it."""
    monkeypatch.setenv("KRTR_PUBLIC_URL", "https://juan-alvarezo-2002--krtr.modal.run/")

    assert CsrfConfig.from_environment().allowed_origin == (
        "https://juan-alvarezo-2002--krtr.modal.run"
    )


def test_the_local_server_is_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """`krtr back web serve` works without configuration."""
    monkeypatch.delenv("KRTR_PUBLIC_URL", raising=False)

    assert CsrfConfig.from_environment().allowed_origin == "http://localhost:8000"


def test_a_relative_public_url_fails_fast() -> None:
    """A misconfigured URL must stop the check, not silently allow or deny everything."""
    with pytest.raises(ValueError, match="KRTR_PUBLIC_URL"):
        _ = CsrfConfig(public_url="/krtr").allowed_origin
