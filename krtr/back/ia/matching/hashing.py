"""Embeds text as hashed character trigrams: a lexical stand-in that needs no model.

Exists so `krtr back ia` and the catalog tests run without downloading the multilingual
model of phase 2. It scores spelling overlap, not meaning, so it only stands in for the real
model: the thresholds set for it do not carry over.
"""

import zlib

import numpy as np

from krtr.back.ia.matching.base import Embedder
from krtr.back.ia.text import normalize_text

DEFAULT_DIMENSIONS = 2048
TRIGRAM_LENGTH = 3


class HashingEmbedder(Embedder):
    """Counts each word's character trigrams into a fixed-size, normalised vector.

    Exists as the deterministic, offline embedder of phase 1. Built by `engine/factory.py`
    for the CLI.
    """

    def __init__(self, dimensions: int = DEFAULT_DIMENSIONS) -> None:
        """Sets the vector size.

        Args:
            dimensions: How many buckets the trigrams are hashed into.
        """
        self._dimensions = dimensions

    def embed(self, texts: list[str]) -> np.ndarray:
        """Embeds texts as normalised trigram counts.

        Args:
            texts: The texts to embed.

        Returns:
            np.ndarray: one L2-normalised row per text; an all-zero row for text with no letters.
        """
        matrix = np.zeros((len(texts), self._dimensions), dtype=np.float32)
        for row, text in enumerate(texts):
            for trigram in _trigrams(normalize_text(text)):
                matrix[row, zlib.crc32(trigram.encode()) % self._dimensions] += 1.0
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        return np.divide(matrix, norms, out=np.zeros_like(matrix), where=norms > 0)


def _trigrams(normalized_text: str) -> list[str]:
    """Splits each word, padded with spaces, into overlapping character trigrams.

    Args:
        normalized_text: Text already passed through `normalize_text`.

    Returns:
        list[str]: the trigrams of every word, so "saldo" yields " sa", "sal", ..., "do ".
    """
    trigrams: list[str] = []
    for word in normalized_text.split():
        padded = f" {word} "
        trigrams.extend(padded[i : i + TRIGRAM_LENGTH] for i in range(len(padded) - 2))
    return trigrams
