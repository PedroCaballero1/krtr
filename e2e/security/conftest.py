"""Shared setup of the production security suite (task 7.2): URLs, QA accounts and a real login.

Exists so every test hits the deployed krtr-web and Keycloak exactly as a browser does. The
URLs default to production (D11) and can be pointed elsewhere with --base-url (the option of
pytest-base-url, installed with pytest-playwright) and --auth-url. QA
accounts (D4) come from `data/credentials/qa_credentials.csv`, never from the repository.
Run with `uv run pytest e2e/security`; tests marked `slow` only run with `--run-slow`.
"""

import csv
import html
import re
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

from krtr.database.neon.client import NeonClient
from krtr.database.neon.config import NeonConfig

PRODUCTION_URL = "https://juan-alvarezo-2002--krtr.modal.run"
PRODUCTION_AUTH_URL = "https://juan-alvarezo-2002--krtr-auth.modal.run"
QA_CREDENTIALS = Path("data/credentials/qa_credentials.csv")
LOCKOUT_ACCOUNT_ROW = 50  # The QA account (row of the CSV, 1-based) the lockout test locks.
SLOW_MARKER = "slow"
TIMEOUT_SECONDS = 60
_FORM_ACTION = re.compile(r'<form[^>]*id="kc-form-login"[^>]*action="([^"]+)"', re.S)


def pytest_addoption(parser: pytest.Parser) -> None:
    """Adds the Keycloak URL and --run-slow options (--base-url comes from pytest-base-url).

    Args:
        parser: pytest's option parser.

    Returns:
        None.
    """
    parser.addoption("--auth-url", default=PRODUCTION_AUTH_URL, help="Keycloak URL.")
    parser.addoption("--run-slow", action="store_true", help="Also run the slow tests.")


def pytest_configure(config: pytest.Config) -> None:
    """Registers the `slow` marker, for tests that wait minutes (e.g. the idle timeout).

    Args:
        config: pytest's configuration.

    Returns:
        None.
    """
    config.addinivalue_line("markers", f"{SLOW_MARKER}: waits minutes; runs with --run-slow.")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skips the slow tests unless --run-slow is given, so the default run stays short.

    Args:
        config: pytest's configuration.
        items: The collected tests.

    Returns:
        None.
    """
    if config.getoption("--run-slow"):
        return
    skip_slow = pytest.mark.skip(reason="slow: run with --run-slow")
    for item in items:
        if SLOW_MARKER in item.keywords:
            item.add_marker(skip_slow)


@pytest.fixture(scope="session")
def base_url(request: pytest.FixtureRequest) -> str:
    """Returns the krtr-web URL under test (production unless --base-url is given)."""
    return (request.config.getoption("--base-url") or PRODUCTION_URL).rstrip("/")


@pytest.fixture(scope="session")
def auth_url(request: pytest.FixtureRequest) -> str:
    """Returns the Keycloak URL under test."""
    return request.config.getoption("--auth-url").rstrip("/")


@pytest.fixture(scope="session")
def qa_accounts() -> list[tuple[str, str]]:
    """Returns the QA accounts, or skips the tests that need them."""
    if not QA_CREDENTIALS.exists():
        pytest.skip(f"{QA_CREDENTIALS} not found")
    with QA_CREDENTIALS.open() as file:
        return [(row["customer_id"], row["password"]) for row in csv.DictReader(file)]


@pytest.fixture(scope="session")
def lockout_account(qa_accounts: list[tuple[str, str]]) -> tuple[str, str]:
    """Returns the one QA account the lockout test may lock; no other test uses it."""
    return qa_accounts[LOCKOUT_ACCOUNT_ROW - 1]


@pytest.fixture(scope="session")
def production_database() -> Iterator[NeonClient]:
    """Yields a client for the Neon database in NEON_DB_HOST (.env), or skips without it."""
    try:
        config = NeonConfig.from_environment()
    except ValueError as missing:
        pytest.skip(str(missing))
    client = NeonClient(config)
    yield client
    client.close()


def new_browser() -> httpx.Client:
    """Returns a client that keeps cookies per host, like a browser."""
    return httpx.Client(timeout=TIMEOUT_SECONDS, follow_redirects=True)


def log_in(browser: httpx.Client, base_url: str, username: str, password: str) -> httpx.Response:
    """Logs in through the real Keycloak form and returns the final response (/app).

    Args:
        browser: The client, which keeps the cookies.
        base_url: krtr-web's URL.
        username: The customer ID.
        password: Its password.

    Returns:
        httpx.Response: the response after the last redirect.
    """
    page = browser.get(f"{base_url}/auth/login?lang=es")
    action = html.unescape(_FORM_ACTION.search(page.text).group(1))
    return browser.post(action, data={"username": username, "password": password})


def csrf_headers(browser: httpx.Client, base_url: str) -> dict[str, str]:
    """Returns the headers the SPA adds to a state-changing request."""
    return {"Origin": base_url, "X-KRTR-CSRF": browser.cookies.get("__Host-krtr_csrf") or ""}
