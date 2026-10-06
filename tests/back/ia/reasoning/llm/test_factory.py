"""Tests the LLM factory: none builds nothing and never loads the ONNX runtime."""

import subprocess
import sys
from pathlib import Path

import pytest

from krtr.back.ia.reasoning.llm.config import LlmConfig
from krtr.back.ia.reasoning.llm.factory import build_llm_client
from krtr.back.ia.reasoning.llm.models import LlmModel

NO_RUNTIME_CHECK = """
import sys
from pathlib import Path
from krtr.back.ia.reasoning.llm.config import LlmConfig
from krtr.back.ia.reasoning.llm.factory import build_llm_client
from krtr.back.ia.reasoning.llm.models import LlmModel
assert build_llm_client(LlmModel.NONE, Path("unused"), LlmConfig()) is None
sys.exit(1 if "onnxruntime_genai" in sys.modules else 0)
"""


def test_none_never_imports_the_llm_runtime() -> None:
    """Tests and LLM-free deployments don't pay for loading onnxruntime-genai."""
    assert subprocess.run([sys.executable, "-c", NO_RUNTIME_CHECK], check=False).returncode == 0


def test_a_real_model_without_its_converted_build_fails_clearly(tmp_path: Path) -> None:
    """Startup fails pointing at the README, not on the first doubtful turn."""
    with pytest.raises(FileNotFoundError, match="README"):
        build_llm_client(LlmModel.QWEN2_5_1_5B_INSTRUCT, tmp_path, LlmConfig())
