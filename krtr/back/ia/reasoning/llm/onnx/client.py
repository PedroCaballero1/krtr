"""Runs a local ONNX LLM with onnxruntime-genai, its output constrained to a JSON schema.

Exists as the client of the local Hugging Face models (`LlmModel.QWEN2_5_1_5B_INSTRUCT`): CPU,
no per-token cost, and the conversation never leaves the container. Generation is guided by the
answer's JSON schema (LLGuidance), so the text always parses; it stops at the time budget, and
then the caller falls back to the deterministic path. Imported only by `reasoning/llm/factory.py`
when such a model is selected, so `none` never loads the runtime.
"""

import json
import logging
import time
from pathlib import Path

import onnxruntime_genai as og
from pydantic import ValidationError

from krtr.back.ia.reasoning.llm.base import LlmClient, LlmUnavailable, SchemaT
from krtr.back.ia.reasoning.llm.config import LlmConfig

logger = logging.getLogger(__name__)

GUIDANCE_TYPE = "json_schema"


class OnnxGenAiClient(LlmClient):
    """Generates schema-constrained answers with one local model.

    Exists so the model is loaded once per process and every call shares it.
    """

    def __init__(self, model_dir: Path, config: LlmConfig) -> None:
        """Loads the converted model and its tokenizer.

        Args:
            model_dir: The folder of the converted ONNX build (with its `genai_config.json`).
            config: The time budget and the answer size.

        Raises:
            FileNotFoundError: if the folder doesn't hold a converted build.
        """
        if not (model_dir / "genai_config.json").is_file():
            raise FileNotFoundError(
                f"No converted LLM in {model_dir}; see README > Conversation agent > LLM"
            )
        logger.info("Loading the LLM from %s", model_dir)
        self._model = og.Model(str(model_dir))
        self._tokenizer = og.Tokenizer(self._model)
        self._config = config

    def complete(self, prompt: str, schema: type[SchemaT]) -> SchemaT:
        """Generates one answer, guided by the schema, within the time budget.

        Args:
            prompt: The full instruction, with the customer's text inside it.
            schema: The pydantic model the answer must validate against.

        Returns:
            SchemaT: the validated answer.

        Raises:
            LlmUnavailable: on timeout, a runtime error, or an answer that doesn't validate.
        """
        try:
            text = self._generate(prompt, json.dumps(schema.model_json_schema()))
            return schema.model_validate_json(text)
        except (RuntimeError, ValidationError) as error:
            raise LlmUnavailable(str(error)) from error

    def _generate(self, prompt: str, json_schema: str) -> str:
        """Runs the token loop until the answer ends, the size limit, or the time budget.

        Args:
            prompt: The instruction.
            json_schema: The answer's JSON schema, as text.

        Returns:
            str: the generated JSON text.

        Raises:
            LlmUnavailable: if the time budget runs out first.
        """
        chat = self._tokenizer.apply_chat_template(
            json.dumps([{"role": "user", "content": prompt}]), add_generation_prompt=True
        )
        params = og.GeneratorParams(self._model)
        params.set_search_options(max_length=8192, do_sample=False)
        params.set_guidance(GUIDANCE_TYPE, json_schema)
        generator = og.Generator(self._model, params)
        generator.append_tokens(self._tokenizer.encode(chat))
        deadline = time.perf_counter() + self._config.timeout_seconds
        tokens: list[int] = []
        while not generator.is_done() and len(tokens) < self._config.max_new_tokens:
            if time.perf_counter() > deadline:
                raise LlmUnavailable("The LLM ran out of its time budget")
            generator.generate_next_token()
            tokens.append(int(generator.get_next_tokens()[0]))
        return self._tokenizer.decode(tokens)
