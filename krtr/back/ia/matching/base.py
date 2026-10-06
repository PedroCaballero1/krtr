"""Defines the contract of the models that turn text into vectors.

Exists so the catalog and the matcher depend on "something that embeds text", and the local
multilingual model (phase 2), the hashing embedder and test fakes can replace each other.
Consumed by `matching/catalog.py` and `engine/`.
"""

from abc import ABC, abstractmethod

import numpy as np


class Embedder(ABC):
    """Turns texts into unit-length vectors, so a dot product is their cosine similarity."""

    @abstractmethod
    def embed(self, texts: list[str]) -> np.ndarray:
        """Embeds texts.

        Args:
            texts: The texts to embed.

        Returns:
            np.ndarray: one L2-normalised row per text, in the same order.
        """
