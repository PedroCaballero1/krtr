"""Tests the LLM Enum: every member is described, and real models name their weights."""

import pytest
from pydantic import ValidationError

from krtr.back.ia.reasoning.llm.models import LLM_MODELS, LlmModel, LlmModelSpec


def test_every_model_has_a_spec_and_none_is_deterministic() -> None:
    """The deterministic option is a selectable member, not a hidden default."""
    assert set(LLM_MODELS) == set(LlmModel)
    assert LLM_MODELS[LlmModel.NONE].deterministic
    assert LLM_MODELS[LlmModel.QWEN2_5_1_5B_INSTRUCT].source == "Qwen/Qwen2.5-1.5B-Instruct"


def test_a_real_model_without_its_weights_is_rejected() -> None:
    """The factory couldn't know which build to load."""
    with pytest.raises(ValidationError, match="source and a local_dir"):
        LlmModelSpec(deterministic=False, source="Qwen/X")
