"""Keeps the customers' cases behind one interface (task 4.8, G18).

Exists so the routes never know where cases live. The case table, its statuses and its
summaries belong to another vertical (G17, out of scope of the web guide); until it exists,
`StubCaseRepository` keeps cases in memory: two sample cases per customer plus the ones they
open. Every lookup matches `incident_id` **and** `customer_id` exactly, so another customer's
case is indistinguishable from one that does not exist. Consumed by `krtr/back/web/app.py` and
`krtr/back/web/routers/`.
"""

import logging
import operator
import secrets
import threading
from datetime import timedelta
from typing import Protocol

from krtr.back.security.clock import Clock, utc_now
from krtr.back.web.cases.artifacts import CaseSummary

logger = logging.getLogger(__name__)

INCIDENT_ID_PREFIX = "INC-"
_INCIDENT_ID_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # No 0/O or 1/I to misread.
_INCIDENT_ID_LENGTH = 10  # 32^10 ≈ 10^15: guessing another customer's ID is hopeless.

# The sample open cases every customer starts with, and how long ago each was opened.
_SAMPLE_CASES = (
    ("Consulta de saldo de la cuenta de ahorros", timedelta(days=2)),
    ("Seguimiento de una queja por un cobro no reconocido", timedelta(days=9)),
)


def new_incident_id() -> str:
    """Generates an unguessable incident ID, such as `INC-7KQ2MZ9XRT`.

    Returns:
        str: a new incident ID, 14 characters long.
    """
    suffix = "".join(secrets.choice(_INCIDENT_ID_ALPHABET) for _ in range(_INCIDENT_ID_LENGTH))
    return f"{INCIDENT_ID_PREFIX}{suffix}"


class CaseRepository(Protocol):
    """What the routes need from wherever cases live. Consumed by `krtr/back/web/routers/`."""

    def list_open(self, customer_id: str) -> list[CaseSummary]:
        """Lists the customer's open cases, newest first.

        Args:
            customer_id: The customer, from the session.

        Returns:
            list[CaseSummary]: the open cases.
        """
        ...

    def create(self, customer_id: str) -> CaseSummary:
        """Opens a new case for the customer.

        Args:
            customer_id: The customer, from the session.

        Returns:
            CaseSummary: the new case.
        """
        ...

    def find_for_customer(self, customer_id: str, incident_id: str) -> CaseSummary | None:
        """Finds one of the customer's open cases by its exact ID.

        Args:
            customer_id: The customer, from the session.
            incident_id: The ID the customer typed or the SPA sent.

        Returns:
            CaseSummary | None: the case, or None if it does not exist **or** is someone else's.
        """
        ...


class StubCaseRepository:
    """Keeps cases in memory, seeding two sample cases the first time a customer is seen.

    Exists so the case screens and the chat work end to end before the case table exists.
    Cases live as long as the process; the krtr-web app runs one container (D8), so every
    request sees the same cases. Thread-safe, because FastAPI runs sync routes in a pool.
    """

    def __init__(self, clock: Clock = utc_now) -> None:
        """Starts with no cases.

        Args:
            clock: Returns the current UTC time; a fake in tests.
        """
        self._clock = clock
        self._cases: dict[str, list[CaseSummary]] = {}
        self._lock = threading.Lock()

    def list_open(self, customer_id: str) -> list[CaseSummary]:
        """Lists the customer's cases, newest first.

        Args:
            customer_id: The customer, from the session.

        Returns:
            list[CaseSummary]: the cases.
        """
        with self._lock:
            cases = list(self._cases_of(customer_id))
        return sorted(cases, key=operator.attrgetter("opened_at"), reverse=True)

    def create(self, customer_id: str) -> CaseSummary:
        """Opens a new case with an empty summary (the chat has not started yet).

        Args:
            customer_id: The customer, from the session.

        Returns:
            CaseSummary: the new case.
        """
        case = CaseSummary(incident_id=new_incident_id(), opened_at=self._clock(), summary="")
        with self._lock:
            self._cases_of(customer_id).append(case)
        logger.info("Opened case %s", case.incident_id)
        return case

    def find_for_customer(self, customer_id: str, incident_id: str) -> CaseSummary | None:
        """Finds one of the customer's cases by its exact ID.

        Args:
            customer_id: The customer, from the session.
            incident_id: The ID to look for.

        Returns:
            CaseSummary | None: the case, or None if it does not exist or is someone else's.
        """
        with self._lock:
            cases = self._cases_of(customer_id)
            return next((case for case in cases if case.incident_id == incident_id), None)

    def _cases_of(self, customer_id: str) -> list[CaseSummary]:
        """Returns the customer's case list, seeding the sample cases on first use.

        Must be called holding the lock.

        Args:
            customer_id: The customer.

        Returns:
            list[CaseSummary]: the customer's (mutable) case list.
        """
        if customer_id not in self._cases:
            now = self._clock()
            self._cases[customer_id] = [
                CaseSummary(incident_id=new_incident_id(), opened_at=now - age, summary=summary)
                for summary, age in _SAMPLE_CASES
            ]
        return self._cases[customer_id]
