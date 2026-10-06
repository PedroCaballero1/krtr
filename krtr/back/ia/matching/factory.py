"""Builds the embedder an `EmbeddingModel` names.

Exists as the one place that maps each model of the Enum to its implementation, so callers
choose a model, never a class. Consumed by `engine/factory.py` and `krtr back ia evaluate`.
"""

from pathlib import Path

from krtr.back.ia.matching.base import Embedder
from krtr.back.ia.matching.hashing import HashingEmbedder
from krtr.back.ia.matching.models import EMBEDDING_MODELS, EmbeddingModel


def build_embedder(model: EmbeddingModel, model_cache: Path) -> Embedder:
    """Builds the embedder of a model.

    The ONNX module is imported here, not at the top, so selecting a deterministic model
    never loads fastembed or its runtime.

    Args:
        model: The selected model.
        model_cache: Where downloaded weights are kept (unused by deterministic models).

    Returns:
        Embedder: the model's embedder, ready to use.
    """
    spec = EMBEDDING_MODELS[model]
    if spec.deterministic:
        return HashingEmbedder(spec.dimensions)
    from krtr.back.ia.matching.onnx.fastembed_embedder import FastEmbedEmbedder

    return FastEmbedEmbedder(str(spec.source), model_cache)
