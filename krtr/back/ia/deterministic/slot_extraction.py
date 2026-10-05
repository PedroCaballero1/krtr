"""Extracts slot values from customer text with keyword and pattern rules, no model involved.

Exists so the deterministic fast path can fill an action's inputs on its own: a product type
named in ES or PT, or an identifier with a known format. Consumed by `deterministic/actions/`.
"""

import re
from collections.abc import Mapping
from enum import StrEnum
from typing import TypeVar

from krtr.back.ia.text import normalize_text

OptionT = TypeVar("OptionT", bound=StrEnum)


def extract_keyword_option(
    text: str, keywords: Mapping[OptionT, tuple[str, ...]]
) -> OptionT | None:
    """Returns the one option whose keywords appear in the text.

    Exists so "saldo de mi tarjeta de crédito" fills `product_type` without a model. If the
    text names two different options, none is returned, so the clarifier asks instead of
    guessing.

    Args:
        text: The raw customer text.
        keywords: For each option, its already-normalised keywords in every language.

    Returns:
        OptionT | None: the option named, or None if none or several are named.
    """
    normalized = f" {normalize_text(text)} "
    named = {
        option
        for option, option_keywords in keywords.items()
        if any(f" {keyword} " in normalized for keyword in option_keywords)
    }
    return named.pop() if len(named) == 1 else None


def extract_pattern(text: str, pattern: re.Pattern[str]) -> str | None:
    """Returns the first match of an identifier pattern, upper-cased.

    Exists so an identifier typed in any case ("c-1234", "C-1234") is looked up the same way.

    Args:
        text: The raw customer text.
        pattern: The identifier's compiled pattern.

    Returns:
        str | None: the identifier, or None if the text has none.
    """
    found = pattern.search(text)
    return found.group().upper() if found else None
