"""Tests how the models are selected: CLI option, then environment, then default, all validated."""

from pathlib import Path

import pytest

from krtr.back.ia.config import IaEnvironmentVariable, IaModelsConfig
from krtr.back.ia.language.models import LanguageDetectorModel
from krtr.back.ia.matching.models import EmbeddingModel


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Starts every test with no model variable set."""
    for variable in IaEnvironmentVariable:
        monkeypatch.delenv(variable, raising=False)


def test_without_options_or_environment_the_defaults_apply() -> None:
    """MiniLM is the default embedder (decision Q2-A); py3langid the only detector."""
    config = IaModelsConfig.resolve()

    assert config.embedding == EmbeddingModel.MULTILINGUAL_MINILM
    assert config.language == LanguageDetectorModel.PY3LANGID
    assert config.model_cache == Path(".krtr") / "models"


def test_the_environment_selects_the_model_and_the_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deployments choose with variables, not code."""
    monkeypatch.setenv(IaEnvironmentVariable.EMBEDDING_MODEL, "hashing")
    monkeypatch.setenv(IaEnvironmentVariable.MODEL_CACHE, "/models")

    config = IaModelsConfig.resolve()

    assert config.embedding == EmbeddingModel.HASHING
    assert config.model_cache == Path("/models")


def test_the_option_wins_over_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """The command line is the most specific choice."""
    monkeypatch.setenv(IaEnvironmentVariable.EMBEDDING_MODEL, "multilingual_minilm")

    config = IaModelsConfig.resolve(embedding=EmbeddingModel.HASHING)

    assert config.embedding == EmbeddingModel.HASHING


def test_an_empty_variable_counts_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """`KRTR_IA_EMBEDDING_MODEL=` in a .env file falls back to the default."""
    monkeypatch.setenv(IaEnvironmentVariable.EMBEDDING_MODEL, "")

    assert IaModelsConfig.resolve().embedding == EmbeddingModel.MULTILINGUAL_MINILM


@pytest.mark.parametrize(
    ("variable", "accepted"),
    [
        (IaEnvironmentVariable.EMBEDDING_MODEL, "'hashing' or 'multilingual_minilm'"),
        (IaEnvironmentVariable.LANGUAGE_MODEL, "'py3langid'"),
    ],
)
def test_an_unknown_model_fails_naming_the_variable_and_the_choices(
    monkeypatch: pytest.MonkeyPatch, variable: IaEnvironmentVariable, accepted: str
) -> None:
    """Only the Enum's members are accepted, and the error says which ones."""
    monkeypatch.setenv(variable, "bert")

    with pytest.raises(ValueError, match=variable.value) as error:
        IaModelsConfig.resolve()

    assert accepted in str(error.value)
