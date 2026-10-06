"""Tests StubCaseRepository: sample cases, new cases, and exact per-customer lookups."""

import re
from concurrent.futures import ThreadPoolExecutor

from krtr.back.web.cases.repository import StubCaseRepository, new_incident_id
from tests.back.security.oidc.fakes import START, FakeClock


def test_a_new_customer_starts_with_two_open_sample_cases() -> None:
    """The support screen needs something to list before the case table exists (G18)."""
    cases = StubCaseRepository(clock=FakeClock()).list_open("A")

    assert len(cases) == 2
    assert all(case.summary for case in cases)
    assert all(case.opened_at < START for case in cases)


def test_the_list_is_stable_and_newest_first() -> None:
    """Listing twice must not reseed, and a newly opened case comes first."""
    repository = StubCaseRepository(clock=FakeClock())
    first = repository.list_open("A")

    created = repository.create("A")
    listed = repository.list_open("A")

    assert listed[0] == created
    assert listed[1:] == first
    assert created.summary == ""


def test_a_customer_finds_only_their_own_case_by_its_exact_id() -> None:
    """A's case is invisible to B, and a near-miss ID is not a match."""
    repository = StubCaseRepository(clock=FakeClock())
    case = repository.create("A")

    assert repository.find_for_customer("A", case.incident_id) == case
    assert repository.find_for_customer("B", case.incident_id) is None
    assert repository.find_for_customer("A", case.incident_id.lower()) is None
    assert repository.find_for_customer("A", case.incident_id[:-1]) is None


def test_customers_never_share_cases() -> None:
    """Each customer's sample cases have their own IDs."""
    repository = StubCaseRepository(clock=FakeClock())

    ids_a = {case.incident_id for case in repository.list_open("A")}
    ids_b = {case.incident_id for case in repository.list_open("B")}

    assert ids_a.isdisjoint(ids_b)


def test_incident_ids_are_unguessable_and_fit_the_messages_table() -> None:
    """IDs are random, readable, and at most 30 characters (`messages.incident_id`)."""
    ids = {new_incident_id() for _ in range(1000)}

    assert len(ids) == 1000
    assert all(re.fullmatch(r"INC-[A-HJ-NP-Z2-9]{10}", incident_id) for incident_id in ids)


def test_concurrent_requests_seed_a_customer_once() -> None:
    """Sync routes run in a thread pool; a race must not give one customer two sets of cases."""
    repository = StubCaseRepository(clock=FakeClock())

    with ThreadPoolExecutor(max_workers=8) as pool:
        listings = list(pool.map(repository.list_open, ["A"] * 32))

    assert all(listing == listings[0] for listing in listings)
    assert len(listings[0]) == 2
