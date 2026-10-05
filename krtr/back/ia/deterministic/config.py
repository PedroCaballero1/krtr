"""Defines the settings of the deterministic actions.

Exists so the formats the slot extractors rely on are declared once instead of inside each
action. Consumed by `deterministic/actions/complaint_status.py` and `engine/factory.py`.
"""

from pydantic import BaseModel

# PROVISIONAL until a real complaint_id sample confirms the format (tasks/todo.md, Q-A):
# an optional letter prefix, an optional dash, and at least four digits.
DEFAULT_COMPLAINT_ID_PATTERN = r"\b[A-Za-z]{0,4}-?\d{4,}\b"


class DeterministicConfig(BaseModel):
    """The deterministic actions' settings.

    Exists so the complaint-status action and its tests share one identifier format.
    Consumed by `engine/factory.py`.
    """

    complaint_id_pattern: str = DEFAULT_COMPLAINT_ID_PATTERN
