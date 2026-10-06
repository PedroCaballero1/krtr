"""Tests the local ONNX client: it refuses a folder without a converted build, and, when the
Qwen build is in the model cache, answers in the schema within its time budget.
"""

from pathlib import Path
from typing import Literal

import pytest
from pydantic import BaseModel

from krtr.back.ia.config import DEFAULT_MODEL_CACHE
from krtr.back.ia.reasoning.llm.config import LlmConfig
from krtr.back.ia.reasoning.llm.models import LLM_MODELS, LlmModel
from krtr.back.ia.reasoning.llm.onnx.client import OnnxGenAiClient

QWEN_BUILD = DEFAULT_MODEL_CACHE / str(LLM_MODELS[LlmModel.QWEN2_5_1_5B_INSTRUCT].local_dir)


class Choice(BaseModel):
    choice: Literal["savings_account", "credit_card", "none"]


def test_a_folder_without_a_converted_build_is_refused(tmp_path: Path) -> None:
    """Loading would fail later and less clearly."""
    with pytest.raises(FileNotFoundError, match="genai|README"):
        OnnxGenAiClient(tmp_path, LlmConfig())


@pytest.mark.skipif(not (QWEN_BUILD / "genai_config.json").is_file(), reason="Qwen not converted")
def test_the_real_model_answers_inside_the_schema() -> None:
    """Guided decoding: the answer parses and is one of the offered options."""
    client = OnnxGenAiClient(QWEN_BUILD, LlmConfig(timeout_seconds=30))
    prompt = (
        "A bank customer was asked which product. Options: savings_account (cuenta de ahorros),"
        ' credit_card (tarjeta de crédito). Reply: "la de la tarjeta". Return the option code.'
    )

    answer = client.complete(prompt, Choice)

    assert answer.choice == "credit_card"
