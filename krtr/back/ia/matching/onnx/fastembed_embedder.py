"""Embeds text with an ONNX sentence-embedding model run by fastembed.

Exists as the embedder of the real models (`EmbeddingModel.MULTILINGUAL_MINILM`): ONNX
runtime, no PyTorch, weights downloaded once into the model cache. Imported only by
`matching/factory.py` when such a model is selected, so `hashing` never loads fastembed.
"""

import logging
from pathlib import Path

import numpy as np
from fastembed import TextEmbedding

from krtr.back.ia.matching.base import Embedder

logger = logging.getLogger(__name__)


class FastEmbedEmbedder(Embedder):
    """Runs one fastembed model and returns L2-normalised vectors.

    Exists so the matcher's dot products stay cosine similarities whatever the model returns.
    """

    def __init__(self, source: str, model_cache: Path) -> None:
        """Loads the model, downloading its weights into the cache the first time.

        Args:
            source: The model's name in the fastembed catalog.
            model_cache: The folder that keeps the downloaded weights.
        """
        logger.info("Loading embedding model %s from %s", source, model_cache)
        self._model = TextEmbedding(model_name=source, cache_dir=str(model_cache))

    def embed(self, texts: list[str]) -> np.ndarray:
        """Embeds texts.

        Args:
            texts: The texts to embed.

        Returns:
            np.ndarray: one L2-normalised row per text, in the same order.
        """
        matrix = np.array(list(self._model.embed(texts)), dtype=np.float32)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        return np.divide(matrix, norms, out=np.zeros_like(matrix), where=norms > 0)
