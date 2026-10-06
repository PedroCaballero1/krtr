"""Load test of the deployed krtr-web with the QA accounts (task 7.5, D7).

Each Locust user is one QA account (D4) with its own session: it logs in through the real
Keycloak form, then uses the API the way the SPA does. Profiles (`--load-profile`):

- `smoke`: 20 users for 3 minutes, to check the script and get first numbers.
- `baseline`: 20 users for 10 minutes; D7 asks for p95 <= 300 ms.
- `spike`: 20 users, a short peak of 50, and back to 20; D7 asks for 0% 5xx.

The app allows 600 requests per minute per IP (4.6) and Locust runs from one IP, so every
request to the app, the login's included, waits for a slot of one shared pacer (8 per second by
default, 80% of the limit). More users therefore means more concurrent sessions, not more
traffic. Requests are named by group: `api` counts for D7's p95; `login` (Keycloak) and `chat`
(the AI engine) are reported apart. At the end the D7 verdict is logged and the exit code is 1
if p95 > 300 ms, any request got a 5xx, or any got a 429 (the pacing failed).

Run: `uv run locust -f e2e/load/locustfile.py --headless --load-profile smoke`.
"""

import logging
import time
from collections import Counter
from enum import StrEnum

import gevent
from locust import HttpUser, LoadTestShape, between, events, task
from locust.argument_parser import LocustArgumentParser
from locust.env import Environment
from locust.exception import StopUser
from locust.stats import StatsEntry
from requests import Response

from e2e.production import PRODUCTION_URL, login_form_action, read_qa_accounts
from krtr.back.security.audit.event_names import EventName

logger = logging.getLogger(__name__)

D7_P95_LIMIT_MS = 300
DEFAULT_APP_REQUESTS_PER_SECOND = 8.0  # 480 a minute, under the app's 600 per IP (D6).
CHAT_INTERVAL_SECONDS = 60  # About one chat message a minute per user (G3 allows 20).
TOO_MANY_REQUESTS = 429
SERVER_ERROR = 500


class LoadProfile(StrEnum):
    """The load shapes `--load-profile` selects (see the module docstring)."""

    SMOKE = "smoke"
    BASELINE = "baseline"
    SPIKE = "spike"


class RequestGroup(StrEnum):
    """The prefix of each request's name, which decides whether it counts for D7's p95."""

    API = "api"  # The backend without AI: what D7's p95 <= 300 ms is about.
    LOGIN = "login"  # Keycloak's form and the OIDC callback.
    CHAT = "chat"  # The AI engine answers it; reported apart.


# Per profile: (end of the stage in seconds since the start, users, users started per second).
PROFILE_STAGES: dict[LoadProfile, list[tuple[int, int, float]]] = {
    LoadProfile.SMOKE: [(180, 20, 1)],
    LoadProfile.BASELINE: [(600, 20, 1)],
    LoadProfile.SPIKE: [(120, 20, 1), (240, 50, 2), (300, 20, 5)],
}


class RequestPacer:
    """Spaces every request to the app so the whole run stays under the per-IP limit.

    Exists because the 600-per-minute limit counts all Locust users together (one IP). Locust
    runs users as gevent greenlets in one process, so one shared instance needs no lock.
    Consumed by `KrtrCustomer` before each request to krtr-web.
    """

    def __init__(self, requests_per_second: float) -> None:
        """Builds a pacer.

        Args:
            requests_per_second: The most requests to the app per second, for all users.
        """
        self._interval_seconds = 1 / requests_per_second
        self._next_slot = 0.0

    def wait_for_slot(self) -> None:
        """Blocks this user until the next free slot, and books it.

        Returns:
            None.
        """
        now = time.monotonic()
        slot = max(now, self._next_slot)
        self._next_slot = slot + self._interval_seconds
        if slot > now:
            gevent.sleep(slot - now)


class AccountPool:
    """Hands each running user its own QA account, and takes it back when the user stops.

    Exists because a second login closes the first session (G15): two users on one account
    would log each other out. Consumed by `KrtrCustomer`.
    """

    def __init__(self, accounts: list[tuple[str, str]]) -> None:
        """Builds the pool.

        Args:
            accounts: (customer_id, password) of each QA account.
        """
        self._free = list(accounts)

    def take(self) -> tuple[str, str]:
        """Takes a free account.

        Returns:
            tuple[str, str]: (customer_id, password).

        Raises:
            StopUser: if every account is in use.
        """
        if not self._free:
            logger.error("No free QA account for another user")
            raise StopUser()
        return self._free.pop(0)

    def give_back(self, account: tuple[str, str]) -> None:
        """Returns an account once its user has logged out.

        Args:
            account: The account the user had.

        Returns:
            None.
        """
        self._free.append(account)


class RunState:
    """What the users share during a run: the pacer, the accounts and the status counts.

    Exists so Locust's event listeners and the users read one object, built when the run
    starts (`on_init`). Consumed by `KrtrCustomer` and the listeners below.
    """

    pacer = RequestPacer(DEFAULT_APP_REQUESTS_PER_SECOND)
    accounts = AccountPool([])
    status_counts: Counter[tuple[str, int]] = Counter()  # (group, status) -> requests.


@events.init_command_line_parser.add_listener
def add_arguments(parser: LocustArgumentParser) -> None:
    """Adds --load-profile and --app-requests-per-second to Locust's command line.

    Args:
        parser: Locust's argument parser.

    Returns:
        None.
    """
    parser.add_argument(
        "--load-profile", choices=[profile.value for profile in LoadProfile], default="smoke"
    )
    parser.add_argument(
        "--app-requests-per-second", type=float, default=DEFAULT_APP_REQUESTS_PER_SECOND
    )


@events.init.add_listener
def on_init(environment: Environment, **_: object) -> None:
    """Builds the run's pacer and account pool from the command line and the QA CSV.

    Args:
        environment: Locust's environment, with the parsed options.

    Returns:
        None.
    """
    rate = environment.parsed_options.app_requests_per_second
    RunState.pacer = RequestPacer(rate)
    RunState.accounts = AccountPool(read_qa_accounts())
    logger.info("Pacing the app at %.1f requests per second", rate)


@events.request.add_listener
def count_status(name: str, response: Response | None, **_: object) -> None:
    """Counts each response by group and status, for the 5xx and 429 checks.

    Args:
        name: The request's name; its first word is the group.
        response: The response (None if the connection failed).

    Returns:
        None.
    """
    status = response.status_code if response is not None else 0
    RunState.status_counts[(name.split(" ", 1)[0], status)] += 1


@events.quitting.add_listener
def check_d7(environment: Environment, **_: object) -> None:
    """Logs the D7 verdict and makes the run fail if it is not met.

    Args:
        environment: Locust's environment, with the run's statistics.

    Returns:
        None.
    """
    api = _group_stats(environment, RequestGroup.API)
    p95 = api.get_response_time_percentile(0.95) if api.num_requests else 0
    server_errors = sum(
        n for (_, status), n in RunState.status_counts.items() if status >= SERVER_ERROR
    )
    rate_limited = sum(
        n for (_, status), n in RunState.status_counts.items() if status == TOO_MANY_REQUESTS
    )
    logger.info(
        "D7: api p95 %d ms over %d requests (limit %d); 5xx: %d; 429: %d",
        p95,
        api.num_requests,
        D7_P95_LIMIT_MS,
        server_errors,
        rate_limited,
    )
    if p95 > D7_P95_LIMIT_MS or server_errors or rate_limited:
        environment.process_exit_code = 1


def _group_stats(environment: Environment, group: RequestGroup) -> StatsEntry:
    """Merges the statistics of every request of one group into a single entry.

    Args:
        environment: Locust's environment.
        group: The group to merge.

    Returns:
        StatsEntry: one entry with all the group's requests, for its percentiles.
    """
    merged = StatsEntry(environment.stats, group.value, "")
    for entry in environment.stats.entries.values():
        if entry.name.startswith(f"{group.value} "):
            merged.extend(entry)
    return merged


class KrtrCustomer(HttpUser):
    """One customer using krtr-web the way the SPA does, with its own QA account.

    Exists as the load the jurors produce (G3): read the session and cases, report activity,
    open and resume cases, send UI events, and now and then a chat message. Run by Locust.
    """

    host = PRODUCTION_URL
    wait_time = between(1, 3)

    def on_start(self) -> None:
        """Takes an account, logs in through Keycloak and opens a case for the chat.

        Returns:
            None.
        """
        self._account = RunState.accounts.take()
        self._log_in()
        self._incident_id = self._open_case()
        self._last_chat = time.monotonic()

    def on_stop(self) -> None:
        """Logs out and frees the account for a later user.

        Returns:
            None.
        """
        self._post(RequestGroup.LOGIN, "/auth/logout")
        RunState.accounts.give_back(self._account)

    @task(4)
    def read_session(self) -> None:
        """GET /api/me, which the SPA calls on every screen."""
        self._get(RequestGroup.API, "/api/me")

    @task(2)
    def report_activity(self) -> None:
        """POST /api/session/activity, which the SPA sends while the user is active."""
        self._post(RequestGroup.API, "/api/session/activity")

    @task(3)
    def list_open_cases(self) -> None:
        """GET /api/cases?status=open, on the home and support screens."""
        self._get(RequestGroup.API, "/api/cases?status=open")

    @task(1)
    def open_and_resume_case(self) -> None:
        """POST /api/cases, then POST /api/cases/resume with the new case."""
        incident_id = self._open_case()
        self._post(RequestGroup.API, "/api/cases/resume", json={"incident_id": incident_id})

    @task(2)
    def send_ui_event(self) -> None:
        """POST /api/events with a page view, as the SPA does on each screen."""
        event = {"event_name": EventName.PAGE_VIEW.value, "properties": {"path": "/app"}}
        self._post(RequestGroup.API, "/api/events", json=event)

    @task(1)
    def load_app_page(self) -> None:
        """GET /app, the SPA's HTML."""
        self._get(RequestGroup.API, "/app")

    @task(2)
    def chat_now_and_then(self) -> None:
        """POST /api/chat/messages, at most once every CHAT_INTERVAL_SECONDS."""
        if time.monotonic() - self._last_chat < CHAT_INTERVAL_SECONDS:
            return
        self._last_chat = time.monotonic()
        message = {"incident_id": self._incident_id, "text": "¿Cuál es mi saldo?", "language": "es"}
        self._post(RequestGroup.CHAT, "/api/chat/messages", json=message)

    def _log_in(self) -> None:
        """Logs in with the real Keycloak form; stops the user if it does not reach /app.

        Returns:
            None.

        Raises:
            StopUser: if the login fails.
        """
        customer_id, password = self._account
        RunState.pacer.wait_for_slot()
        page = self.client.get("/auth/login?lang=es", name="login GET /auth/login")
        RunState.pacer.wait_for_slot()  # The form's redirects reach /auth/callback and /app.
        RunState.pacer.wait_for_slot()
        final = self.client.post(
            login_form_action(page.text),
            data={"username": customer_id, "password": password},
            name="login POST keycloak form",
        )
        if not final.url.endswith("/app"):
            logger.error("A QA account could not log in")
            RunState.accounts.give_back(self._account)
            raise StopUser()

    def _open_case(self) -> str:
        """Opens a case and returns its ID.

        Returns:
            str: the new case's incident_id.
        """
        return self._post(RequestGroup.API, "/api/cases").json()["incident_id"]

    def _get(self, group: RequestGroup, path: str) -> Response:
        """Sends a paced GET to the app, named by its group.

        Args:
            group: Which group the request counts in.
            path: The app path.

        Returns:
            Response: the response.
        """
        RunState.pacer.wait_for_slot()
        return self.client.get(path, name=f"{group.value} GET {path}")

    def _post(
        self, group: RequestGroup, path: str, json: dict[str, object] | None = None
    ) -> Response:
        """Sends a paced POST to the app with the SPA's CSRF headers, named by its group.

        Args:
            group: Which group the request counts in.
            path: The app path.
            json: The JSON body, if any.

        Returns:
            Response: the response.
        """
        RunState.pacer.wait_for_slot()
        headers = {
            "Origin": self.host,
            "X-KRTR-CSRF": self.client.cookies.get("__Host-krtr_csrf") or "",
        }
        return self.client.post(path, json=json, headers=headers, name=f"{group.value} POST {path}")


class KrtrLoadShape(LoadTestShape):
    """Follows the stages of the profile chosen with --load-profile, then stops the run.

    Exists so each profile of task 7.5 is one command, without the web UI. Run by Locust.
    """

    def tick(self) -> tuple[int, float] | None:
        """Returns the users and spawn rate for now, or None when the profile is over.

        Returns:
            tuple[int, float] | None: (users, users started per second), or None to stop.
        """
        elapsed = self.get_run_time()
        profile = LoadProfile(self.runner.environment.parsed_options.load_profile)
        for stage_end, users, spawn_rate in PROFILE_STAGES[profile]:
            if elapsed < stage_end:
                return users, spawn_rate
        return None
