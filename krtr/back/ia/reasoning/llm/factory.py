"""Builds the LLM client an `LlmModel` names.

Exists as the one place that maps each model of the Enum to its implementation. The ONNX
runtime is imported only here, and only when a real model is selected, so `none` never loads
it. Consumed by `engine/factory.py` and `krtr back ia evaluate-llm`.
"""

from pathlib import Path

from krtr.back.ia.reasoning.llm.base import LlmClient
from krtr.back.ia.reasoning.llm.config import LlmConfig
from krtr.back.ia.reasoning.llm.models import LLM_MODELS, LlmModel


def build_llm_client(model: LlmModel, model_cache: Path, config: LlmConfig) -> LlmClient | None:
    """Builds the client of a model.

    Args:
        model: The selected LLM.
        model_cache: The folder holding converted model builds.
        config: The time budget and answer size.

    Returns:
        LlmClient | None: the client, or None for the deterministic `none`.

    Raises:
        FileNotFoundError: if the model's converted build is not in the cache.
    """
    spec = LLM_MODELS[model]
    if spec.deterministic:
        return None
    from krtr.back.ia.reasoning.llm.onnx.client import OnnxGenAiClient

    return OnnxGenAiClient(model_cache / str(spec.local_dir), config)
