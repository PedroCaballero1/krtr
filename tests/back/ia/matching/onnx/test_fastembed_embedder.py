"""Tests the real MiniLM model on ES and PT phrases, when its weights are already downloaded.

Skipped otherwise (e.g. in CI), so the suite never downloads 220 MB; `krtr back ia ask` or
`evaluate` with the default model downloads them into `.krtr/models/`.
"""

import numpy as np
import pytest

from krtr.back.ia.config import DEFAULT_MODEL_CACHE
from krtr.back.ia.matching.base import Embedder
from krtr.back.ia.matching.factory import build_embedder
from krtr.back.ia.matching.models import EmbeddingModel

pytestmark = pytest.mark.skipif(
    not DEFAULT_MODEL_CACHE.is_dir() or not any(DEFAULT_MODEL_CACHE.iterdir()),
    reason="MiniLM weights not downloaded into .krtr/models",
)


@pytest.fixture(scope="module")
def embedder() -> Embedder:
    """Loads MiniLM once for the module."""
    return build_embedder(EmbeddingModel.MULTILINGUAL_MINILM, DEFAULT_MODEL_CACHE)


def test_rows_are_unit_length(embedder: Embedder) -> None:
    """Dot products must be cosine similarities for the matcher."""
    vectors = embedder.embed(["¿Cuál es mi saldo?", "Qual é o meu saldo?"])

    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=1e-5)


def test_the_same_request_in_es_and_pt_is_closer_than_another_request(
    embedder: Embedder,
) -> None:
    """Meaning, not spelling: a PT balance request is near an ES one, far from a complaint."""
    spanish, portuguese, complaint = embedder.embed(
        ["¿Cuál es el saldo de mi cuenta?", "Qual é o saldo da minha conta?", "¿Cómo va mi queja?"]
    )

    assert spanish @ portuguese > spanish @ complaint
