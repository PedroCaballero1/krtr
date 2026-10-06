"""Tests the case routes (task 4.8): listing, opening and resuming, always per customer."""

import pytest

from tests.back.web.fakes import WebHarness, build_harness

NOT_FOUND = {"error": "case_not_found", "message_key": "support_case_not_found"}


@pytest.fixture
def web() -> WebHarness:
    """Builds the app with fake Keycloak, sessions, events and clock."""
    return build_harness()


def test_open_cases_are_listed_with_the_contract_fields(web: WebHarness) -> None:
    """The support screen reads `incident_id`, `opened_at` and `summary` (§3.4)."""
    web.log_in()

    response = web.client.get("/api/cases?status=open")

    assert response.status_code == 200
    assert len(response.json()) == 2
    assert set(response.json()[0]) == {"incident_id", "opened_at", "summary"}


def test_only_open_cases_can_be_listed(web: WebHarness) -> None:
    """The web shows open cases only; other statuses are not part of the contract."""
    web.log_in()

    assert web.client.get("/api/cases?status=closed").status_code == 422
    assert web.client.get("/api/cases").status_code == 422


def test_a_new_case_is_opened_listed_and_resumable(web: WebHarness) -> None:
    """Opening a "Caso nuevo" returns an ID the customer can list and come back to."""
    web.log_in()

    created = web.post("/api/cases")
    incident_id = created.json()["incident_id"]
    listed = web.client.get("/api/cases?status=open").json()
    resumed = web.post("/api/cases/resume", json={"incident_id": incident_id})

    assert created.status_code == 201
    assert listed[0]["incident_id"] == incident_id
    assert resumed.status_code == 200
    assert resumed.json() == {"incident_id": incident_id}


def test_customer_a_cannot_resume_customer_bs_case(web: WebHarness) -> None:
    """The acceptance of 4.8: B's case answers A exactly like a case that does not exist."""
    web.log_in("B")
    b_case = web.post("/api/cases").json()["incident_id"]
    web.log_in("A")

    foreign = web.post("/api/cases/resume", json={"incident_id": b_case})
    missing = web.post("/api/cases/resume", json={"incident_id": "INC-DOESNOTEXI"})

    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json() == NOT_FOUND
    assert b_case not in {
        case["incident_id"] for case in web.client.get("/api/cases?status=open").json()
    }


def test_the_customer_comes_from_the_session_not_the_body(web: WebHarness) -> None:
    """A body naming another customer must not change whose case is opened."""
    web.log_in("A")

    created = web.post("/api/cases", json={"customer_id": "B"}).json()["incident_id"]
    web.log_in("B")

    assert web.post("/api/cases/resume", json={"incident_id": created}).status_code == 404


@pytest.mark.parametrize("incident_id", ["", "X" * 31])
def test_an_id_outside_the_contract_is_rejected(web: WebHarness, incident_id: str) -> None:
    """Empty IDs and IDs longer than `messages.incident_id` never reach the repository."""
    web.log_in()

    assert web.post("/api/cases/resume", json={"incident_id": incident_id}).status_code == 422


@pytest.mark.parametrize(
    ("method", "path"),
    [("GET", "/api/cases?status=open"), ("POST", "/api/cases"), ("POST", "/api/cases/resume")],
)
def test_without_a_session_every_case_route_is_401(web: WebHarness, method: str, path: str) -> None:
    """Cases belong to a customer; with no session there is none to show."""
    response = web.client.request(method, path, json={"incident_id": "INC-X"})

    assert response.status_code == 401


@pytest.mark.parametrize("path", ["/api/cases", "/api/cases/resume"])
def test_opening_and_resuming_need_csrf(web: WebHarness, path: str) -> None:
    """Both change what the customer is working on, so both are state-changing (task 4.5)."""
    web.log_in()

    response = web.client.post(path, json={"incident_id": "INC-X"})

    assert response.status_code == 403
