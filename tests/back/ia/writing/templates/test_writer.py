"""Tests that the templates phrase every fact in both languages and catch gaps when loaded."""

import json
from pathlib import Path

import pytest

from krtr.back.ia.artifacts import MessageKey, ReplyContent
from krtr.back.ia.deterministic.artifacts import ProductType, SlotName
from krtr.back.ia.writing.templates.writer import (
    TEMPLATES_DIRECTORY,
    TemplateResponseWriter,
)
from krtr.back.security.oidc.artifacts import InterfaceLanguage

WRITER = TemplateResponseWriter.load()
BALANCE = ReplyContent(
    message_key=MessageKey.CREDIT_BALANCE,
    values={SlotName.PRODUCT_TYPE: ProductType.CREDIT_CARD.value},
    items=[
        {
            "product_number": "****9921",
            "balance": "10.00",
            "currency": "COP",
            "credit_limit": "50.00",
        }
    ],
)


def test_values_with_a_label_are_translated_per_language() -> None:
    """An enum value is shown in the customer's language, the facts unchanged."""
    spanish = WRITER.write(BALANCE, InterfaceLanguage.SPANISH)
    portuguese = WRITER.write(BALANCE, InterfaceLanguage.PORTUGUESE)

    assert spanish == "Saldo de tarjeta de crédito:\n- ****9921: saldo 10.00 COP, cupo 50.00 COP"
    assert (
        portuguese == "Saldo de cartão de crédito:\n- ****9921: saldo 10.00 COP, limite 50.00 COP"
    )


def test_items_are_one_line_each() -> None:
    """Options are listed one per line, numbered as given."""
    content = ReplyContent(
        message_key=MessageKey.ASK_CHOOSE_OPTION,
        values={"slot": SlotName.PRODUCT_TYPE},
        items=[{"number": "1", "option": "savings_account"}, {"number": "2", "option": "mortgage"}],
    )

    reply = WRITER.write(content, InterfaceLanguage.SPANISH)

    assert reply.splitlines() == [
        "¿Sobre qué producto? Responde con el número:",
        "1. cuenta de ahorros",
        "2. crédito hipotecario",
    ]


def test_a_catalog_missing_a_message_fails_when_loaded(tmp_path: Path) -> None:
    """A message without its PT text would crash a Portuguese conversation."""
    for language in InterfaceLanguage:
        raw = json.loads((TEMPLATES_DIRECTORY / f"{language.value}.json").read_text())
        if language == InterfaceLanguage.PORTUGUESE:
            del raw["messages"][MessageKey.ESCALATED.value]
        (tmp_path / f"{language.value}.json").write_text(json.dumps(raw))

    with pytest.raises(ValueError, match="pt-BR templates miss: escalated"):
        TemplateResponseWriter.load(tmp_path)


def test_a_catalog_missing_a_label_fails_when_loaded(tmp_path: Path) -> None:
    """A value without a label would reach the customer as a raw code."""
    for language in InterfaceLanguage:
        raw = json.loads((TEMPLATES_DIRECTORY / f"{language.value}.json").read_text())
        if language == InterfaceLanguage.SPANISH:
            del raw["labels"][ProductType.MORTGAGE.value]
        (tmp_path / f"{language.value}.json").write_text(json.dumps(raw))

    with pytest.raises(ValueError, match="es templates miss: mortgage"):
        TemplateResponseWriter.load(tmp_path)
