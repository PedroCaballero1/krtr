"""Normalises customer text so every deterministic comparison in `krtr/back/ia/` sees the same form.

Exists because the guardrails (repetition), the slot extractors (keywords) and the hashing
embedder all compare text, and they must agree on case, accents and spacing: "Saldo" and
"saldo ", or "crédito" and "credito", are the same request.
"""

import re
import unicodedata

_WHITESPACE = re.compile(r"\s+")
_PUNCTUATION = re.compile(r"[^\w\s-]")
_FIRST_NUMBER = re.compile(r"\d+")
_IDENTIFIER = re.compile(
    r"\S*\d{3,}\S*"
)  # A token with 3+ digits: an ID, an account number, an amount.


def normalize_text(text: str) -> str:
    """Returns the text lower-cased, without accents or punctuation, and with single spaces.

    Exists so Spanish and Portuguese messages typed with or without accents, or with a
    trailing "?" or ".", compare equal.

    Args:
        text: The raw customer text.

    Returns:
        str: the normalised text.
    """
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    without_punctuation = _PUNCTUATION.sub(" ", without_accents)
    return _WHITESPACE.sub(" ", without_punctuation).strip()


def first_number(text: str) -> int | None:
    """Returns the first whole number written in the text, if any.

    Exists so a reply such as "2", "la 2" or "opção 2" can pick an option from a list.

    Args:
        text: The raw customer text.

    Returns:
        int | None: the first number, or None if the text has no digits.
    """
    found = _FIRST_NUMBER.search(text)
    return int(found.group()) if found else None


def matching_text(text: str) -> str:
    """Returns the text without identifiers, for embedding.

    Exists because an ID such as "PQR-104233" carries no meaning for the matcher but pulls the
    message away from the catalog's phrases. Only the embedding sees this text; the slot
    extractors read the original one.

    Args:
        text: The raw customer text.

    Returns:
        str: the text with every token of 3 or more digits removed.
    """
    return _WHITESPACE.sub(" ", _IDENTIFIER.sub(" ", text)).strip()
