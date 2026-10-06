"""Tests `krtr back ia ask` and `chat`: replies, the clarification flow, and leaving."""

import re

import pytest
from typer.testing import CliRunner

from krtr.back.ia.config import IaEnvironmentVariable
from krtr.back.ia.matching.thresholds import THRESHOLDS_FILE
from krtr.cli.main import app

runner = CliRunner()


def test_ask_answers_one_message() -> None:
    """A clear request comes back resolved, with the demo customer's balance."""
    result = runner.invoke(app, ["back", "ia", "ask", "Saldo de mi cuenta de ahorros"])

    assert result.exit_code == 0, result.output
    assert re.search(
        r"\[resolved · \d+\.\d{2} ms\] Saldo de cuenta de ahorros:\n- \*{4}7781: 2,350,400\.50 COP",
        result.output,
    )


def test_ask_replies_in_portuguese() -> None:
    """`--language pt-BR` switches the templates."""
    result = runner.invoke(
        app, ["back", "ia", "ask", "saldo da minha conta poupança", "--language", "pt-BR"]
    )

    assert result.exit_code == 0, result.output
    assert "Saldo de conta poupança:" in result.output


def test_ask_rejects_a_blank_message() -> None:
    """A blank message is a usage error, not a turn."""
    result = runner.invoke(app, ["back", "ia", "ask", "   "])

    assert result.exit_code == 2


def test_chat_keeps_the_conversation_across_turns_until_exit() -> None:
    """The question and its answer are two turns of the same conversation."""
    result = runner.invoke(app, ["back", "ia", "chat"], input="¿Cuál es mi saldo?\n3\n/exit\n")

    assert result.exit_code == 0, result.output
    assert re.search(r"\[needs_clarification · [\d.]+ ms\] ¿Sobre qué producto\?", result.output)
    assert re.search(r"\[resolved · [\d.]+ ms\] Saldo de tarjeta de crédito:", result.output)


def test_chat_stops_when_the_conversation_ends() -> None:
    """After a closure there is nothing left to ask, so the loop ends by itself."""
    result = runner.invoke(app, ["back", "ia", "chat"], input="hola banco\n" * 3)

    assert result.exit_code == 0, result.output
    assert "[closed · " in result.output


def test_ask_detects_portuguese_without_the_language_option() -> None:
    """`--language` is only the starting point: Portuguese text gets a Portuguese reply."""
    result = runner.invoke(
        app, ["back", "ia", "ask", "Preciso consultar o saldo do meu cartão de crédito"]
    )

    assert result.exit_code == 0, result.output
    assert "Saldo de cartão de crédito:" in result.output


def test_an_unknown_model_in_the_environment_exits_naming_the_choices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A typo in KRTR_IA_EMBEDDING_MODEL fails before any message, listing the valid values."""
    monkeypatch.setenv(IaEnvironmentVariable.EMBEDDING_MODEL, "bert")

    result = runner.invoke(app, ["back", "ia", "ask", "hola"])

    assert result.exit_code == 1
    assert "KRTR_IA_EMBEDDING_MODEL" in result.output
    assert "'hashing' or 'multilingual_minilm'" in result.output


def test_an_unknown_model_option_is_rejected_by_the_cli() -> None:
    """The option only accepts the Enum's values."""
    result = runner.invoke(app, ["back", "ia", "ask", "hola", "--embedding-model", "bert"])

    assert result.exit_code == 2


def test_the_option_overrides_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """`--embedding-model` wins over an invalid environment value."""
    monkeypatch.setenv(IaEnvironmentVariable.EMBEDDING_MODEL, "bert")

    result = runner.invoke(
        app, ["back", "ia", "ask", "Saldo de ahorros", "--embedding-model", "hashing"]
    )

    assert result.exit_code == 0, result.output


def test_evaluate_reports_both_languages_without_writing() -> None:
    """The report shows each language's outcomes; without --write nothing is saved."""
    before = THRESHOLDS_FILE.read_text()

    result = runner.invoke(app, ["back", "ia", "evaluate"])

    assert result.exit_code == 0, result.output
    assert "Embedding model: hashing" in result.output
    assert "[es]" in result.output and "[pt-BR]" in result.output
    assert re.search(r"proposed: right \d+ · wrong 0", result.output)
    assert THRESHOLDS_FILE.read_text() == before
