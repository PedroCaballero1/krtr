"""Tests the keyword and pattern rules that fill slots without a model."""

import re

from krtr.back.ia.deterministic.actions.account_balance import PRODUCT_KEYWORDS
from krtr.back.ia.deterministic.artifacts import ProductType
from krtr.back.ia.deterministic.config import DEFAULT_COMPLAINT_ID_PATTERN
from krtr.back.ia.deterministic.slot_extraction import (
    extract_keyword_option,
    extract_pattern,
)


def test_keyword_option_is_found_in_spanish_and_portuguese() -> None:
    """The same product is named in either language, with or without accents."""
    assert extract_keyword_option("Saldo de mi tarjeta de crédito", PRODUCT_KEYWORDS) == (
        ProductType.CREDIT_CARD
    )
    assert extract_keyword_option("saldo do cartao de credito", PRODUCT_KEYWORDS) == (
        ProductType.CREDIT_CARD
    )


def test_keyword_must_be_a_whole_word() -> None:
    """A keyword inside another word does not count ("ahorro" inside "ahorrolandia")."""
    assert extract_keyword_option("ahorrolandia", PRODUCT_KEYWORDS) is None


def test_two_different_options_give_none_so_the_customer_is_asked() -> None:
    """Naming two products is ambiguous: no guess is made."""
    text = "mi cuenta de ahorros y mi tarjeta de crédito"
    assert extract_keyword_option(text, PRODUCT_KEYWORDS) is None


def test_pattern_is_upper_cased_and_absent_ids_give_none() -> None:
    """IDs typed in lower case are looked up as stored; no ID gives None."""
    pattern = re.compile(DEFAULT_COMPLAINT_ID_PATTERN)
    assert extract_pattern("es el pqr-104233, gracias", pattern) == "PQR-104233"
    assert extract_pattern("no tengo el número", pattern) is None
