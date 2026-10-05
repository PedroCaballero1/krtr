"""Defines the requests krtr can answer deterministically.

Exists as the closed catalog the matcher and the clarifier may choose from: nothing outside
it can reach an action. Consumed by `deterministic/`, `matching/` (one exemplar file per
member) and `writing/templates/` (one label per member).
"""

from enum import StrEnum


class Intent(StrEnum):
    """A request with a deterministic action behind it.

    Exists so every intent is one typed value from the matcher to the action registry, and
    the exemplar files are validated against it. Seeded from the call history (every call
    opens with a balance request) and the complaints table.
    """

    ACCOUNT_BALANCE = "account_balance"
    COMPLAINT_STATUS = "complaint_status"
