"""Defines the case routes: list open cases, open a new one, and resume one (task 4.8, §3.4).

Exists so the support screen (G18) can show the customer's open cases and start or resume the
chat on one of them. The customer always comes from the session, never from the request body,
and a case that does not exist answers exactly like another customer's case (the same 404), so
the response reveals nothing about other customers' IDs. Consumed by `krtr/back/web/app.py`.
"""

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from krtr.back.security.sessions.artifacts import SessionRecord
from krtr.back.web.cases.artifacts import (
    CaseReference,
    CaseStatus,
    CaseSummary,
    ResumeCaseRequest,
)
from krtr.back.web.cases.repository import CaseRepository
from krtr.back.web.csrf import require_session_with_csrf
from krtr.back.web.dependencies import require_session
from krtr.back.web.errors import ApiErrorCode, MessageKey, api_error

logger = logging.getLogger(__name__)

cases_router = APIRouter(prefix="/api/cases")


def get_case_repository(request: Request) -> CaseRepository:
    """Returns the app's case repository.

    Args:
        request: The current request, to reach the app's state.

    Returns:
        CaseRepository: the repository `create_app` was built with.
    """
    return request.app.state.case_repository


@cases_router.get("")
def list_cases(
    status: CaseStatus,
    session: SessionRecord = Depends(require_session),
    cases: CaseRepository = Depends(get_case_repository),
) -> list[CaseSummary]:
    """Lists the customer's open cases (the only status the web shows).

    Args:
        status: Which cases to list; only `open` is accepted (anything else is 422).
        session: The request's live session.
        cases: The case repository.

    Returns:
        list[CaseSummary]: `[{incident_id, opened_at, summary}]`, newest first.
    """
    logger.debug("Listing %s cases", status.value)
    return cases.list_open(session.customer_id)


@cases_router.post("", status_code=201)
def create_case(
    session: SessionRecord = Depends(require_session_with_csrf),
    cases: CaseRepository = Depends(get_case_repository),
) -> CaseReference:
    """Opens a new case for the customer ("Caso nuevo").

    Args:
        session: The request's live session, past the CSRF checks.
        cases: The case repository.

    Returns:
        CaseReference: the new case's `incident_id`.
    """
    case = cases.create(session.customer_id)
    return CaseReference(incident_id=case.incident_id)


@cases_router.post("/resume", response_model=CaseReference)
def resume_case(
    payload: ResumeCaseRequest,
    session: SessionRecord = Depends(require_session_with_csrf),
    cases: CaseRepository = Depends(get_case_repository),
) -> CaseReference | JSONResponse:
    """Resumes one of the customer's open cases by its exact ID.

    Args:
        payload: The incident ID the customer typed.
        session: The request's live session, past the CSRF checks.
        cases: The case repository.

    Returns:
        CaseReference | JSONResponse: the case's `incident_id`, or 404 `case_not_found` when it
        does not exist or belongs to another customer (the same answer for both).
    """
    case = cases.find_for_customer(session.customer_id, payload.incident_id)
    if case is None:
        return case_not_found()
    return CaseReference(incident_id=case.incident_id)


def case_not_found() -> JSONResponse:
    """Builds the one 404 for a missing case and for another customer's case.

    Exists so the case routes and the chat routes answer an unknown case identically.

    Returns:
        JSONResponse: 404 with the §3.4 body.
    """
    return api_error(404, ApiErrorCode.CASE_NOT_FOUND, MessageKey.CASE_NOT_FOUND)
