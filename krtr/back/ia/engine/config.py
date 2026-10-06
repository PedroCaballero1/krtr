"""Groups the settings every part of the engine needs.

Exists so `build_engine` takes one configuration object instead of one argument per
sub-vertical. Consumed by `engine/factory.py`.
"""

from pydantic import BaseModel, Field

from krtr.back.ia.config import IaConfig
from krtr.back.ia.deterministic.config import DeterministicConfig
from krtr.back.ia.language.config import LanguageConfig
from krtr.back.ia.matching.config import CatalogConfig, MatchThresholds


class EngineConfig(BaseModel):
    """The engine's settings, each with its sub-vertical's defaults.

    Exists so tests and callers override only what they need. Consumed by `build_engine`.
    """

    conversation: IaConfig = Field(default_factory=IaConfig)
    deterministic: DeterministicConfig = Field(default_factory=DeterministicConfig)
    thresholds: MatchThresholds = Field(default_factory=MatchThresholds)
    catalog: CatalogConfig = Field(default_factory=CatalogConfig)
    language: LanguageConfig = Field(default_factory=LanguageConfig)
