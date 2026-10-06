"""Tests that every embedding model is described and that downloaded ones name their weights."""

import pytest
from pydantic import ValidationError

from krtr.back.ia.matching.models import EMBEDDING_MODELS, EmbeddingModel, EmbeddingModelSpec


def test_every_model_of_the_enum_has_a_spec() -> None:
    """A member without a spec could be selected but never built."""
    assert set(EMBEDDING_MODELS) == set(EmbeddingModel)


def test_the_enum_lists_the_deterministic_stand_in() -> None:
    """The deterministic embedder is a selectable model too, not a hidden test helper."""
    assert EMBEDDING_MODELS[EmbeddingModel.HASHING].deterministic
    assert not EMBEDDING_MODELS[EmbeddingModel.MULTILINGUAL_MINILM].deterministic


def test_a_downloaded_model_without_a_source_is_rejected() -> None:
    """The factory could not know which weights to fetch."""
    with pytest.raises(ValidationError, match="needs a source"):
        EmbeddingModelSpec(deterministic=False, dimensions=384)
