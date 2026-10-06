"""Runs the `krtr back ia` CLI tests on the hashing model, so they never download weights."""

import pytest

from krtr.back.ia.config import IaEnvironmentVariable
from krtr.back.ia.matching.models import EmbeddingModel


@pytest.fixture(autouse=True)
def hashing_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """Selects the offline, deterministic embedder through the environment, as a user would."""
    monkeypatch.setenv(IaEnvironmentVariable.EMBEDDING_MODEL, EmbeddingModel.HASHING.value)
