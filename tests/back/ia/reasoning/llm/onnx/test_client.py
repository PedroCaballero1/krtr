"""Tests the local ONNX client: it refuses a folder without a converted build, and, when the
Qwen build is in the model cache, answers in the schema within the time it is given.
"""

import time
from pathlib import Path
from typing import Literal

import pytest
from pydantic import BaseModel

from krtr.back.ia.config import DEFAULT_MODEL_CACHE
from krtr.back.ia.reasoning.llm.base import LlmUnavailable
from krtr.back.ia.reasoning.llm.config import LlmConfig
from krtr.back.ia.reasoning.llm.models import LLM_MODELS, LlmModel
from krtr.back.ia.reasoning.llm.onnx.client import OnnxGenAiClient

QWEN_BUILD = DEFAULT_MODEL_CACHE / str(LLM_MODELS[LlmModel.QWEN2_5_1_5B_INSTRUCT].local_dir)


PROMPT = (
    "A bank customer was asked which product. Options: savings_account (cuenta de ahorros),"
    ' credit_card (tarjeta de crédito). Reply: "la de la tarjeta". Return the option code.'
)


# About 3,000 characters of earlier conversation: reading it takes about 3 s on CPU.
LONG_HISTORY = "Customer: quiero saber el saldo de mi cuenta, por favor\n" * 55


class Choice(BaseModel):
    choice: Literal["savings_account", "credit_card", "none"]


def test_a_folder_without_a_converted_build_is_refused(tmp_path: Path) -> None:
    """Loading would fail later and less clearly."""
    with pytest.raises(FileNotFoundError, match="genai|README"):
        OnnxGenAiClient(tmp_path, LlmConfig())


@pytest.mark.skipif(not (QWEN_BUILD / "genai_config.json").is_file(), reason="Qwen not converted")
def test_the_real_model_answers_inside_the_schema() -> None:
    """Guided decoding: the answer parses and is one of the offered options."""
    client = OnnxGenAiClient(QWEN_BUILD, LlmConfig())

    answer = client.complete(PROMPT, Choice, timeout_seconds=30)

    assert answer.choice == "credit_card"


@pytest.mark.skipif(not (QWEN_BUILD / "genai_config.json").is_file(), reason="Qwen not converted")
def test_reading_the_prompt_counts_against_the_time_given() -> None:
    """A long prompt takes seconds to read; generating the short answer takes well under 1.5 s.

    Timing only the generation (the old behaviour) would let this call through; counting the
    read, it fails as soon as the read ends.
    """
    client = OnnxGenAiClient(QWEN_BUILD, LlmConfig())
    started_at = time.perf_counter()

    with pytest.raises(LlmUnavailable, match="time"):
        client.complete(LONG_HISTORY + PROMPT, Choice, timeout_seconds=1.5)

    assert time.perf_counter() - started_at > 1.5
