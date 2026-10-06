"""Builds the language detector a `LanguageDetectorModel` names.

Exists as the one place that maps each detector of the Enum to its implementation. Consumed
by `engine/factory.py`.
"""

from krtr.back.ia.language.base import LanguageDetector
from krtr.back.ia.language.models import LanguageDetectorModel
from krtr.back.ia.language.py3langid_detector import Py3LangidLanguageDetector

DETECTORS: dict[LanguageDetectorModel, type[LanguageDetector]] = {
    LanguageDetectorModel.PY3LANGID: Py3LangidLanguageDetector,
}


def build_language_detector(model: LanguageDetectorModel) -> LanguageDetector:
    """Builds the detector of a model.

    Args:
        model: The selected detector.

    Returns:
        LanguageDetector: the detector, ready to use.
    """
    return DETECTORS[model]()
