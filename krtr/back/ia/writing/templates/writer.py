"""Phrases replies from the ES and PT template catalogs.

Exists as the default writer: it costs nothing, answers in microseconds (G16) and can only
show the facts it is given, so a deterministic answer stays deterministic. The catalogs are
`<language>.json` files next to this module. Consumed by `engine/factory.py`.
"""

import json
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel

from krtr.back.ia.artifacts import MessageKey, ReplyContent
from krtr.back.ia.deterministic.artifacts import ComplaintStatus, ProductType, SlotName
from krtr.back.ia.deterministic.intents import Intent
from krtr.back.ia.writing.base import ResponseWriter
from krtr.back.security.oidc.artifacts import InterfaceLanguage

TEMPLATES_DIRECTORY = Path(__file__).parent

# Every value of these sets can appear in a reply, so each needs a label in every language.
LABELLED_ENUMS: tuple[type[StrEnum], ...] = (Intent, ProductType, ComplaintStatus, SlotName)


class MessageTemplate(BaseModel):
    """One message: its text, and the line repeated for each item (if it lists any)."""

    text: str
    item: str | None = None


class TemplateCatalog(BaseModel):
    """One language's messages and the labels its values are shown with."""

    messages: dict[MessageKey, MessageTemplate]
    labels: dict[str, str]


class TemplateResponseWriter(ResponseWriter):
    """Fills the language's template with the reply's facts, translating known values.

    Exists as the phase 1 writer. Built with `TemplateResponseWriter.load`.
    """

    def __init__(self, catalogs: dict[InterfaceLanguage, TemplateCatalog]) -> None:
        """Keeps one catalog per language.

        Args:
            catalogs: The validated catalog of every supported language.
        """
        self._catalogs = catalogs

    @classmethod
    def load(cls, directory: Path = TEMPLATES_DIRECTORY) -> "TemplateResponseWriter":
        """Reads and validates the catalog of every supported language.

        Args:
            directory: The folder holding `<language>.json`.

        Returns:
            TemplateResponseWriter: the writer.

        Raises:
            FileNotFoundError: if a language has no catalog.
            ValueError: if a catalog misses a message or a label.
        """
        catalogs = {language: _load_catalog(directory, language) for language in InterfaceLanguage}
        return cls(catalogs)

    def write(self, content: ReplyContent, language: InterfaceLanguage) -> str:
        """Fills the message's text and one item line per item.

        Args:
            content: The message key and the facts it may show.
            language: The customer's language.

        Returns:
            str: the reply, one line per item after the text.
        """
        catalog = self._catalogs[language]
        template = catalog.messages[content.message_key]
        lines = [template.text.format(**_localize(content.values, catalog.labels))]
        if template.item is not None:
            lines.extend(
                template.item.format(**_localize(item, catalog.labels)) for item in content.items
            )
        return "\n".join(lines)


def _load_catalog(directory: Path, language: InterfaceLanguage) -> TemplateCatalog:
    """Reads one language's catalog and checks it covers every message and label.

    Args:
        directory: The folder holding `<language>.json`.
        language: The language to read.

    Returns:
        TemplateCatalog: the validated catalog.

    Raises:
        ValueError: listing the missing messages or labels.
    """
    raw = json.loads((directory / f"{language.value}.json").read_text(encoding="utf-8"))
    catalog = TemplateCatalog.model_validate(raw)
    missing = [key.value for key in MessageKey if key not in catalog.messages]
    missing += [
        member.value
        for enum in LABELLED_ENUMS
        for member in enum
        if member.value not in catalog.labels
    ]
    if missing:
        raise ValueError(f"The {language.value} templates miss: {', '.join(missing)}")
    return catalog


def _localize(values: dict[str, str], labels: dict[str, str]) -> dict[str, str]:
    """Replaces each value that has a label with its label.

    Args:
        values: The facts, e.g. `{"product_type": "credit_card"}`.
        labels: The language's labels.

    Returns:
        dict[str, str]: the facts ready to show, e.g. `{"product_type": "tarjeta de crédito"}`.
    """
    return {str(name): labels.get(value, value) for name, value in values.items()}
