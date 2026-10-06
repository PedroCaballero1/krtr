"""Shared facts about the deployed krtr-web for the suites under e2e/ (D9).

Exists so the security suite (e2e/security) and the load test (e2e/load) agree on the
production URLs (D11), where the QA accounts (D4) live and how to find Keycloak's login form,
instead of each keeping its own copy. The accounts are read from
`data/credentials/qa_credentials.csv`, never from the repository.
"""

import csv
import html
import re
from pathlib import Path

PRODUCTION_URL = "https://juan-alvarezo-2002--krtr.modal.run"
PRODUCTION_AUTH_URL = "https://juan-alvarezo-2002--krtr-auth.modal.run"
QA_CREDENTIALS = Path("data/credentials/qa_credentials.csv")
_FORM_ACTION = re.compile(r'<form[^>]*id="kc-form-login"[^>]*action="([^"]+)"', re.S)


def read_qa_accounts() -> list[tuple[str, str]]:
    """Reads the QA accounts, in the CSV's order (row 1 first).

    Returns:
        list[tuple[str, str]]: (customer_id, password) per QA account.

    Raises:
        FileNotFoundError: if the CSV is not there.
    """
    with QA_CREDENTIALS.open() as file:
        return [(row["customer_id"], row["password"]) for row in csv.DictReader(file)]


def login_form_action(login_page: str) -> str:
    """Finds where Keycloak's login form posts to.

    Args:
        login_page: The HTML of Keycloak's login page.

    Returns:
        str: the form's action URL, unescaped.

    Raises:
        ValueError: if the page has no login form (e.g. Keycloak answered an error page).
    """
    match = _FORM_ACTION.search(login_page)
    if match is None:
        raise ValueError("Keycloak's login form is not on the page")
    return html.unescape(match.group(1))
