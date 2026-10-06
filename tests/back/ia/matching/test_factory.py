"""Tests that each embedding model builds its embedder, and hashing never loads fastembed."""

import subprocess
import sys
from pathlib import Path

from krtr.back.ia.matching.factory import build_embedder
from krtr.back.ia.matching.hashing import HashingEmbedder
from krtr.back.ia.matching.models import EmbeddingModel

NO_FASTEMBED_CHECK = """
import sys
from pathlib import Path
from krtr.back.ia.matching.factory import build_embedder
from krtr.back.ia.matching.models import EmbeddingModel
build_embedder(EmbeddingModel.HASHING, Path("unused"))
sys.exit(1 if "fastembed" in sys.modules or "onnxruntime" in sys.modules else 0)
"""


def test_hashing_builds_the_deterministic_embedder() -> None:
    """The deterministic member maps to the trigram embedder."""
    assert isinstance(build_embedder(EmbeddingModel.HASHING, Path("unused")), HashingEmbedder)


def test_hashing_never_imports_the_onnx_runtime() -> None:
    """Offline use and the tests must not pay for loading fastembed (checked in a clean process)."""
    result = subprocess.run([sys.executable, "-c", NO_FASTEMBED_CHECK], check=False)

    assert result.returncode == 0
