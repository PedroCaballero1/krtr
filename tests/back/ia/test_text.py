"""Tests the text normalisation every deterministic comparison relies on."""

import pytest

from krtr.back.ia.text import first_number, normalize_text


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  Tarjeta de CRÉDITO?  ", "tarjeta de credito"),
        ("Cartão   de\tcrédito.", "cartao de credito"),
        ("¿Cuál es mi saldo?", "cual es mi saldo"),
        ("PQR-104233", "pqr-104233"),
    ],
)
def test_normalize_text_ignores_case_accents_punctuation_and_spacing(
    raw: str, expected: str
) -> None:
    """Accents, case, punctuation and repeated spaces never make two requests differ."""
    assert normalize_text(raw) == expected


@pytest.mark.parametrize(("raw", "expected"), [("2", 2), ("la opción 3", 3), ("opção 12 ou 4", 12)])
def test_first_number_reads_the_first_number(raw: str, expected: int) -> None:
    """The first number in a reply is the option it picks."""
    assert first_number(raw) == expected


def test_first_number_is_none_without_digits() -> None:
    """A reply with no digits picks no option."""
    assert first_number("la segunda") is None
