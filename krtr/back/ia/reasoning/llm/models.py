"""Lists every LLM the agent can run for its doubtful turns, the deterministic option included.

Exists so the LLM is chosen from a closed, validated set (`KRTR_IA_LLM_MODEL` or `--llm-model`),
like the embedder and the language detector, and each choice's traits live next to its name.
Consumed by `krtr/back/ia/config.py` and `reasoning/llm/factory.py`.
"""

from enum import StrEnum

from pydantic import BaseModel, model_validator


class LlmModel(StrEnum):
    """An LLM the agent can run."""

    NONE = "none"  # No LLM: the template clarifier only. Deterministic; the tests and fallback.
    QWEN2_5_1_5B_INSTRUCT = "qwen2_5_1_5b_instruct"  # Local, CPU, int4 ONNX; the default.


class LlmModelSpec(BaseModel):
    """What the factory needs to know about one LLM."""

    deterministic: bool  # Runs no model at all.
    source: str | None = None  # The official Hugging Face repo the ONNX build is made from.
    local_dir: str | None = None  # The converted ONNX build's folder, inside the model cache.

    @model_validator(mode="after")
    def _weights_for_real_models(self) -> "LlmModelSpec":
        """Checks that every real model names its source and its converted folder.

        Returns:
            LlmModelSpec: the validated spec.

        Raises:
            ValueError: if a non-deterministic model lacks `source` or `local_dir`.
        """
        if not self.deterministic and not (self.source and self.local_dir):
            raise ValueError("A non-deterministic LLM needs a source and a local_dir")
        return self


LLM_MODELS: dict[LlmModel, LlmModelSpec] = {
    LlmModel.NONE: LlmModelSpec(deterministic=True),
    LlmModel.QWEN2_5_1_5B_INSTRUCT: LlmModelSpec(
        deterministic=False,
        source="Qwen/Qwen2.5-1.5B-Instruct",
        local_dir="qwen2_5_1_5b_instruct_int4_cpu",
    ),
}
