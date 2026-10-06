"""Defines the conversation rules and the model selection of the `krtr/back/ia/` vertical.

Exists so the limits that bound a conversation — how many clarifications before escalating
(G19, G20) and how many repeats before closing (G13) — and which models run are declared once.
Consumed by `reasoning/resolver.py`, `guardrails/policy.py`, `engine/factory.py` and the CLI.
"""

import logging
import os
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from krtr.back.ia.language.models import LanguageDetectorModel
from krtr.back.ia.matching.models import EmbeddingModel
from krtr.back.ia.reasoning.llm.models import LlmModel

logger = logging.getLogger(__name__)

DEFAULT_MODEL_CACHE = Path(".krtr") / "models"  # Git-ignored, like the rest of `.krtr/`.


class IaEnvironmentVariable(StrEnum):
    """The environment variables `IaModelsConfig` reads.

    Exists so the config loader, the README, the Modal image and the tests never disagree on
    spelling.
    """

    EMBEDDING_MODEL = "KRTR_IA_EMBEDDING_MODEL"  # A value of `EmbeddingModel`.
    LANGUAGE_MODEL = "KRTR_IA_LANGUAGE_MODEL"  # A value of `LanguageDetectorModel`.
    LLM_MODEL = "KRTR_IA_LLM_MODEL"  # A value of `LlmModel`.
    MODEL_CACHE = "KRTR_IA_MODEL_CACHE"  # Where downloaded model weights are kept.


class IaConfig(BaseModel):
    """The conversation limits.

    Exists so the resolver, the guardrails and their tests share the same numbers instead of
    repeating them. Consumed by `reasoning/resolver.py` and `guardrails/policy.py`.
    """

    max_clarification_turns: int = Field(default=3, ge=1)  # Over it, the case is escalated.
    repetition_limit: int = Field(default=3, ge=2)  # The same message this many times closes it.
    recent_messages_kept: int = Field(default=10, ge=2)  # Window for the repetition rule.


class IaModelsConfig(BaseModel):
    """Which models the agent runs, each one a validated Enum member.

    Exists so an unknown model name fails when the engine is built, listing the accepted
    values, instead of when the first message arrives. Consumed by `engine/factory.py`.
    """

    embedding: EmbeddingModel = EmbeddingModel.MULTILINGUAL_MINILM
    language: LanguageDetectorModel = LanguageDetectorModel.PY3LANGID
    llm: LlmModel = LlmModel.QWEN2_5_1_5B_INSTRUCT
    model_cache: Path = DEFAULT_MODEL_CACHE

    @classmethod
    def resolve(
        cls,
        embedding: EmbeddingModel | None = None,
        language: LanguageDetectorModel | None = None,
        llm: LlmModel | None = None,
    ) -> "IaModelsConfig":
        """Picks each model from the CLI option, else the environment, else the default.

        Args:
            embedding: The `--embedding-model` option, if given.
            language: The `--language-model` option, if given.
            llm: The `--llm-model` option, if given.

        Returns:
            IaModelsConfig: the validated selection.

        Raises:
            ValueError: naming the variable, if an environment value is not a known model.
        """
        values = {name: value for name, value in _environment_values().items() if value is not None}
        if embedding is not None:
            values["embedding"] = embedding
        if language is not None:
            values["language"] = language
        if llm is not None:
            values["llm"] = llm
        try:
            config = cls.model_validate(values)
        except ValidationError as error:
            raise ValueError(f"Invalid model selection: {_describe(error)}") from error
        logger.info(
            "Models: embedding %s, language %s, LLM %s",
            config.embedding,
            config.language,
            config.llm,
        )
        return config


def _environment_values() -> dict[str, str | None]:
    """Reads the model variables, mapped to the config's field names.

    Returns:
        dict[str, str | None]: each field's raw environment value, or None if unset or empty.
    """
    return {
        "embedding": os.environ.get(IaEnvironmentVariable.EMBEDDING_MODEL) or None,
        "language": os.environ.get(IaEnvironmentVariable.LANGUAGE_MODEL) or None,
        "llm": os.environ.get(IaEnvironmentVariable.LLM_MODEL) or None,
        "model_cache": os.environ.get(IaEnvironmentVariable.MODEL_CACHE) or None,
    }


def _describe(error: ValidationError) -> str:
    """Names each invalid variable with the values it accepts.

    Args:
        error: Pydantic's validation error.

    Returns:
        str: e.g. "KRTR_IA_EMBEDDING_MODEL: Input should be 'hashing' or 'multilingual_minilm'".
    """
    variables = {
        "embedding": IaEnvironmentVariable.EMBEDDING_MODEL,
        "language": IaEnvironmentVariable.LANGUAGE_MODEL,
        "llm": IaEnvironmentVariable.LLM_MODEL,
        "model_cache": IaEnvironmentVariable.MODEL_CACHE,
    }
    return "; ".join(
        f"{variables[str(item['loc'][0])].value}: {item['msg']}" for item in error.errors()
    )
