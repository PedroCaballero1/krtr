"""Lists every language detector the agent can run.

Exists so the detector is chosen from a closed, validated set (`KRTR_IA_LANGUAGE_MODEL` or
`--language-model`), like the embedding model. Consumed by `krtr/back/ia/config.py` and
`language/factory.py`.
"""

from enum import StrEnum


class LanguageDetectorModel(StrEnum):
    """A language detector the agent can run."""

    PY3LANGID = "py3langid"  # Deterministic n-gram identifier, offline, limited to ES / PT.
