"""Runs the `krtr back ia` CLI tests on deterministic models, so they never download weights."""

import pytest

from krtr.back.ia.config import IaEnvironmentVariable
from krtr.back.ia.matching.models import EmbeddingModel
from krtr.back.ia.reasoning.llm.models import LlmModel


@pytest.fixture(autouse=True)
def deterministic_models(monkeypatch: pytest.MonkeyPatch) -> None:
    """Selects the offline embedder and no LLM through the environment, as a user would."""
    monkeypatch.setenv(IaEnvironmentVariable.EMBEDDING_MODEL, EmbeddingModel.HASHING.value)
    monkeypatch.setenv(IaEnvironmentVariable.LLM_MODEL, LlmModel.NONE.value)
