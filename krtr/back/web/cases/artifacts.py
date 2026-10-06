"""Defines the contracts of krtr-web's case endpoints (task 4.8, §3.4).

Exists so the case list, the new case and the resumed case have one typed shape each, shared by
the repository and the routes. Consumed by `krtr/back/web/cases/repository.py` and
`krtr/back/web/routers/cases.py`.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

INCIDENT_ID_MAX_LENGTH = 30  # `messages.incident_id` is VARCHAR(30).


class CaseStatus(StrEnum):
    """The case statuses `GET /api/cases?status=` accepts; the web only lists open cases (G18)."""

    OPEN = "open"


class CaseSummary(BaseModel):
    """One open case, as `GET /api/cases?status=open` lists it."""

    incident_id: str
    opened_at: datetime
    summary: str


class CaseReference(BaseModel):
    """The `{incident_id}` that `POST /api/cases` and `POST /api/cases/resume` return."""

    incident_id: str


class ResumeCaseRequest(BaseModel):
    """The `POST /api/cases/resume` body: the incident ID the customer typed."""

    incident_id: str = Field(min_length=1, max_length=INCIDENT_ID_MAX_LENGTH)
