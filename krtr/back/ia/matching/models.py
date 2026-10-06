"""Lists every embedding model the agent can run, deterministic stand-ins included.

Exists so the embedder is chosen from a closed, validated set (`KRTR_IA_EMBEDDING_MODEL` or
`--embedding-model`), never from a free string, and each choice's traits live next to its name.
Consumed by `krtr/back/ia/config.py`, `matching/factory.py` and `matching/thresholds.py`.
"""

from enum import StrEnum

from pydantic import BaseModel, model_validator


class EmbeddingModel(StrEnum):
    """An embedding model the agent can run.

    Exists so the selection is validated against the models this code knows how to build.
    """

    HASHING = "hashing"  # Deterministic character trigrams: offline, for tests and no-network use.
    MULTILINGUAL_MINILM = "multilingual_minilm"  # The default: ES / PT sentence embeddings.


class EmbeddingModelSpec(BaseModel):
    """What the factory needs to know about one embedding model."""

    deterministic: bool  # Same input, same vector, with no downloaded weights.
    source: str | None = None  # The model's name in the fastembed catalog, for ONNX models.
    dimensions: int

    @model_validator(mode="after")
    def _source_for_downloaded_models(self) -> "EmbeddingModelSpec":
        """Checks that every non-deterministic model names the weights to download.

        Returns:
            EmbeddingModelSpec: the validated spec.

        Raises:
            ValueError: if a non-deterministic model has no `source`.
        """
        if not self.deterministic and not self.source:
            raise ValueError("A non-deterministic embedding model needs a source")
        return self


EMBEDDING_MODELS: dict[EmbeddingModel, EmbeddingModelSpec] = {
    EmbeddingModel.HASHING: EmbeddingModelSpec(deterministic=True, dimensions=2048),
    EmbeddingModel.MULTILINGUAL_MINILM: EmbeddingModelSpec(
        deterministic=False,
        source="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        dimensions=384,
    ),
}
