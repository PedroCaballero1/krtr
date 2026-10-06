"""Loads the evaluation set from `messages/<language>/`.

Exists so the labelled messages live as plain text, one per line in `<label>.txt` (the same
cheap format as the catalog), and the repetition pairs as `kind<TAB>first<TAB>second` lines in
`repetition.tsv`. The set is never reused as catalog phrases, so the thresholds are not set
on the catalog's own examples. Consumed by `matching/evaluation/runner.py`.
"""

from pathlib import Path

from krtr.back.ia.deterministic.intents import Intent
from krtr.back.ia.matching.evaluation.artifacts import (
    NO_INTENT_LABEL,
    REPETITION_FILE,
    EvaluationCase,
    EvaluationSet,
    PairKind,
    RepetitionPair,
)
from krtr.back.ia.matching.labels import GuardLabel
from krtr.back.security.oidc.artifacts import InterfaceLanguage

# Not `data/`: the repository ignores every folder with that name (it is reserved for datasets).
EVALUATION_DIRECTORY = Path(__file__).parent / "messages"
PAIR_FIELDS = 3


def load_evaluation_set(directory: Path = EVALUATION_DIRECTORY) -> EvaluationSet:
    """Reads every language's labelled messages and repetition pairs.

    Args:
        directory: The folder holding one subfolder per language.

    Returns:
        EvaluationSet: the cases and pairs.

    Raises:
        ValueError: on an unknown label file or a malformed pair line.
    """
    cases: list[EvaluationCase] = []
    pairs: list[RepetitionPair] = []
    for language in InterfaceLanguage:
        folder = directory / language.value
        for path in sorted(folder.glob("*.txt")):
            expected = _parse_label(path.stem)
            cases.extend(
                EvaluationCase(language=language, expected=expected, text=line)
                for line in _lines(path)
            )
        pairs.extend(_read_pairs(folder / REPETITION_FILE, language))
    return EvaluationSet(cases=cases, pairs=pairs)


def _parse_label(stem: str) -> Intent | GuardLabel | None:
    """Maps a file name to what its messages must reach.

    Args:
        stem: The file name without its suffix.

    Returns:
        Intent | GuardLabel | None: the expected intent or guard, or None for `none.txt`.

    Raises:
        ValueError: if the name is none of them.
    """
    if stem == NO_INTENT_LABEL:
        return None
    for label_type in (Intent, GuardLabel):
        if stem in label_type._value2member_map_:
            return label_type(stem)
    raise ValueError(f"Evaluation file {stem!r} is not an Intent, a GuardLabel or 'none'")


def _read_pairs(path: Path, language: InterfaceLanguage) -> list[RepetitionPair]:
    """Reads one language's repetition pairs, if the file exists.

    Args:
        path: The `repetition.tsv` file.
        language: The pairs' language.

    Returns:
        list[RepetitionPair]: the pairs, empty without a file.

    Raises:
        ValueError: if a line does not have exactly three tab-separated fields.
    """
    if not path.is_file():
        return []
    pairs = []
    for line in _lines(path):
        fields = line.split("\t")
        if len(fields) != PAIR_FIELDS:
            raise ValueError(f"{path}: expected kind<TAB>first<TAB>second, got {line!r}")
        kind, first, second = fields
        pairs.append(
            RepetitionPair(language=language, kind=PairKind(kind), first=first, second=second)
        )
    return pairs


def _lines(path: Path) -> list[str]:
    """Reads a file's non-blank lines, stripped.

    Args:
        path: The file.

    Returns:
        list[str]: its lines.
    """
    return [line.strip() for line in path.read_text("utf-8").splitlines() if line.strip()]
