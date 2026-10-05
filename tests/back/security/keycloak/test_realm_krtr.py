"""Tests realm-krtr.json: the krtr realm keeps task 3.2's security settings and holds no secret."""

import json
import re
from pathlib import Path
from typing import Any

import pytest

REALM_FILE = Path(__file__).resolve().parents[4] / "krtr/back/security/keycloak/realm-krtr.json"
WEB_CALLBACKS = [
    "http://localhost:8000/auth/callback",
    "https://juan-alvarezo-2002--krtr.modal.run/auth/callback",
]


@pytest.fixture(scope="module")
def realm() -> dict[str, Any]:
    """Loads the realm file once for every test in this module."""
    return json.loads(REALM_FILE.read_text())


def client_named(realm: dict[str, Any], client_id: str) -> dict[str, Any]:
    """Returns the realm's client with the given clientId."""
    return next(client for client in realm["clients"] if client["clientId"] == client_id)


def test_realm_file_holds_no_secret_value() -> None:
    """A re-export must not leak a secret or key: only the client secret's placeholder may stay."""
    text = REALM_FILE.read_text()

    assert "**********" not in text
    assert '"privateKey"' not in text
    assert re.findall(r'"secret"\s*:\s*"([^"]*)"', text) == ["${KRTR_WEB_OIDC_CLIENT_SECRET}"]


def test_no_self_service_account_management(realm: dict[str, Any]) -> None:
    """D5: users can neither register, reset nor change a password, nor open the account console."""
    assert not realm["registrationAllowed"]
    assert not realm["resetPasswordAllowed"]
    assert not realm["rememberMe"]
    assert not client_named(realm, "account-console")["enabled"]


def test_brute_force_locks_for_15_minutes_after_5_failures(realm: dict[str, Any]) -> None:
    """G3: after 5 failures the account refuses logins for 15 minutes."""
    assert realm["bruteForceProtected"] and not realm["permanentLockout"]
    assert (
        realm["failureFactor"],
        realm["waitIncrementSeconds"],
        realm["maxFailureWaitSeconds"],
    ) == (
        5,
        900,
        900,
    )


def test_session_lifetimes_follow_g15(realm: dict[str, Any]) -> None:
    """G15: sessions end after 5 idle minutes or 30 minutes in total; access tokens last 5."""
    lifetimes = (
        realm["ssoSessionIdleTimeout"],
        realm["ssoSessionMaxLifespan"],
        realm["accessTokenLifespan"],
    )

    assert lifetimes == (300, 1800, 300)


def test_login_flow_keeps_one_session_per_user(realm: dict[str, Any]) -> None:
    """G15: a new login ends the user's previous session instead of adding one."""
    forms = next(
        flow for flow in realm["authenticationFlows"] if flow["alias"] == "krtr browser forms"
    )
    limiter = next(
        step
        for step in forms["authenticationExecutions"]
        if step.get("authenticator") == "user-session-limits"
    )
    config = next(
        c for c in realm["authenticatorConfig"] if c["alias"] == limiter["authenticatorConfig"]
    )

    assert realm["browserFlow"] == "krtr browser"
    assert limiter["requirement"] == "REQUIRED"
    assert (config["config"]["userRealmLimit"], config["config"]["behavior"]) == (
        "1",
        "Terminate oldest session",
    )


def test_web_client_is_confidential_with_pkce_and_exact_callbacks(realm: dict[str, Any]) -> None:
    """The BFF client uses its secret and PKCE S256, no password grant, and only the 2 callbacks."""
    web = client_named(realm, "krtr-web")

    assert not web["publicClient"]
    assert not web["directAccessGrantsEnabled"] and not web["implicitFlowEnabled"]
    assert web["attributes"]["pkce.code.challenge.method"] == "S256"
    assert sorted(web["redirectUris"]) == WEB_CALLBACKS


def test_login_is_offered_in_spanish_and_portuguese(realm: dict[str, Any]) -> None:
    """G14/D14: Spanish and Brazilian Portuguese, Spanish by default."""
    assert realm["internationalizationEnabled"]
    assert sorted(realm["supportedLocales"]) == ["es", "pt-BR"]
    assert realm["defaultLocale"] == "es"


def test_profile_never_asks_for_email_or_names(realm: dict[str, Any]) -> None:
    """D5: emails and names are not imported, so login neither requires nor accepts them."""
    provider = realm["components"]["org.keycloak.userprofile.UserProfileProvider"][0]
    profile = json.loads(provider["config"]["kc.user.profile.config"][0])
    required = {attribute["name"] for attribute in profile["attributes"] if "required" in attribute}

    assert required.isdisjoint({"email", "firstName", "lastName"})
    assert not realm["loginWithEmailAllowed"] and realm["duplicateEmailsAllowed"]


def test_login_and_admin_events_are_kept_90_days(realm: dict[str, Any]) -> None:
    """G21: Keycloak keeps its events 90 days, for task 4.10 to sync them into `events`."""
    assert realm["eventsEnabled"] and realm["adminEventsEnabled"]
    assert realm["eventsExpiration"] == 90 * 24 * 60 * 60
