"""Tests the API error contract: every message key the backend sends has ES and PT text."""

import json
from pathlib import Path

import pytest

from krtr.back.web.errors import MessageKey

LOCALES_DIRECTORY = Path(__file__).parents[3] / "krtr" / "front" / "src" / "i18n" / "locales"


@pytest.mark.parametrize("locale", ["es", "pt-BR"])
def test_every_message_key_is_translated(locale: str) -> None:
    """A key missing from the SPA's locales would show the raw key to the customer."""
    translations = json.loads((LOCALES_DIRECTORY / f"{locale}.json").read_text(encoding="utf-8"))

    missing = sorted(key.value for key in MessageKey if key.value not in translations)

    assert missing == []
