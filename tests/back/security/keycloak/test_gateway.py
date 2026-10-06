"""Tests the Keycloak gateway (task 3.7, D19).

Acceptance: blocked paths answer 404 without reaching Keycloak, several Set-Cookie headers come
through, 302 redirects are passed on unchanged, and a timeout answers 504.
"""

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from krtr.back.security.keycloak.config import GatewayConfig
from krtr.back.security.keycloak.gateway import build_gateway, normalize_path

KEYCLOAK = "http://127.0.0.1:8081"
PUBLIC_HOST = "juan-alvarezo-2002--krtr-auth.modal.run"
LOGIN_PAGE = "/realms/krtr/protocol/openid-connect/auth"


@pytest.fixture
def keycloak() -> respx.MockRouter:
    """Stands in for Keycloak on 127.0.0.1:8081; any unexpected call fails the test."""
    with respx.mock(base_url=KEYCLOAK, assert_all_called=False) as router:
        yield router


@pytest.fixture
def gateway(keycloak: respx.MockRouter) -> TestClient:
    """The gateway as Modal serves it, in front of the stand-in Keycloak."""
    return TestClient(build_gateway(GatewayConfig(public_host=PUBLIC_HOST)))


@pytest.mark.parametrize(
    "path",
    [
        "/admin/",
        "/admin/master/console/",
        "/admin/realms/krtr/users",
        "/realms/master/protocol/openid-connect/token",
        "/metrics",
        "/health",
        "/health/ready",
        "/realms/..//admin/realms",
        "/realms/krtr/../master/protocol/openid-connect/auth",
        "/ADMIN/realms",
        "/admin;jsessionid=x/realms",
        "/%61dmin/realms",
    ],
)
def test_hidden_endpoints_are_404_without_reaching_keycloak(
    gateway: TestClient, keycloak: respx.MockRouter, path: str
) -> None:
    """No spelling of an admin or operational path may reach Keycloak (D19)."""
    any_call = keycloak.route().mock(return_value=httpx.Response(200))

    response = gateway.get(path)

    assert response.status_code == 404
    assert not any_call.called


def test_a_login_page_is_forwarded_with_its_query(
    gateway: TestClient, keycloak: respx.MockRouter
) -> None:
    """The OIDC authorization request reaches Keycloak exactly as the browser sent it."""
    login = keycloak.get(LOGIN_PAGE).mock(return_value=httpx.Response(200, text="<form>"))

    response = gateway.get(f"{LOGIN_PAGE}?client_id=krtr-web&state=abc&ui_locales=pt-BR")

    assert response.status_code == 200
    assert response.text == "<form>"
    assert login.calls.last.request.url.params["ui_locales"] == "pt-BR"


def test_a_form_post_keeps_its_method_body_and_cookies(
    gateway: TestClient, keycloak: respx.MockRouter
) -> None:
    """The login form's POST carries the credentials and Keycloak's session cookies."""
    action = "/realms/krtr/login-actions/authenticate"
    submit = keycloak.post(action).mock(return_value=httpx.Response(200))

    gateway.post(
        f"{action}?session_code=s",
        content=b"username=12345678&password=secret",
        headers={
            "content-type": "application/x-www-form-urlencoded",
            "cookie": "AUTH_SESSION_ID=a",
        },
    )

    sent = submit.calls.last.request
    assert sent.content == b"username=12345678&password=secret"
    assert sent.headers["cookie"] == "AUTH_SESSION_ID=a"
    assert sent.url.params["session_code"] == "s"


def test_every_set_cookie_comes_through(gateway: TestClient, keycloak: respx.MockRouter) -> None:
    """Keycloak sets several cookies at once; merging them would break the login."""
    keycloak.get(LOGIN_PAGE).mock(
        return_value=httpx.Response(
            200,
            headers=[
                ("set-cookie", "AUTH_SESSION_ID=a; Path=/realms/krtr/; Secure; HttpOnly"),
                ("set-cookie", "KC_RESTART=b; Path=/realms/krtr/; Secure; HttpOnly"),
                ("set-cookie", "KEYCLOAK_IDENTITY=c; Path=/realms/krtr/; Secure; HttpOnly"),
            ],
        )
    )

    response = gateway.get(LOGIN_PAGE)

    cookies = response.headers.get_list("set-cookie")
    assert [cookie.split("=", 1)[0] for cookie in cookies] == [
        "AUTH_SESSION_ID",
        "KC_RESTART",
        "KEYCLOAK_IDENTITY",
    ]


def test_a_redirect_is_passed_on_unchanged(gateway: TestClient, keycloak: respx.MockRouter) -> None:
    """The redirect back to krtr-web with the code must reach the browser, not be followed."""
    location = "https://juan-alvarezo-2002--krtr.modal.run/auth/callback?code=c&state=s"
    keycloak.post("/realms/krtr/login-actions/authenticate").mock(
        return_value=httpx.Response(302, headers={"location": location})
    )

    response = gateway.post("/realms/krtr/login-actions/authenticate", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == location


def test_forwarding_headers_come_from_the_connection_not_the_client(
    gateway: TestClient, keycloak: respx.MockRouter
) -> None:
    """Spoofed forwarding headers are dropped; Keycloak sees the real peer and public host."""
    page = keycloak.get(LOGIN_PAGE).mock(return_value=httpx.Response(200))

    gateway.get(
        LOGIN_PAGE,
        headers={
            "X-Forwarded-For": "203.0.113.7",
            "X-Forwarded-Host": "evil.example",
            "X-Real-IP": "203.0.113.8",
            "Forwarded": "for=203.0.113.9",
        },
    )

    sent = page.calls.last.request.headers
    assert sent.get_list("x-forwarded-for") == ["testclient"]
    assert sent["x-forwarded-host"] == PUBLIC_HOST
    assert sent["x-forwarded-proto"] == "https"
    assert "x-real-ip" not in sent
    assert "forwarded" not in sent


def test_a_slow_keycloak_answers_504(gateway: TestClient, keycloak: respx.MockRouter) -> None:
    """A stuck Keycloak must not hang the login; the browser gets a gateway timeout."""
    keycloak.get(LOGIN_PAGE).mock(side_effect=httpx.ReadTimeout("slow"))

    assert gateway.get(LOGIN_PAGE).status_code == 504


def test_an_unreachable_keycloak_answers_502(
    gateway: TestClient, keycloak: respx.MockRouter
) -> None:
    """While Keycloak is still starting, the gateway reports a bad gateway, not a crash."""
    keycloak.get(LOGIN_PAGE).mock(side_effect=httpx.ConnectError("refused"))

    assert gateway.get(LOGIN_PAGE).status_code == 502


def test_hardening_headers_are_added_and_server_removed(
    gateway: TestClient, keycloak: respx.MockRouter
) -> None:
    """Keycloak's own policies are kept; what it lacks is added; Server never leaks."""
    keycloak.get(LOGIN_PAGE).mock(
        return_value=httpx.Response(
            200,
            headers={
                "content-security-policy": "frame-ancestors 'self'",
                "referrer-policy": "no-referrer",
                "server": "Vert.x",
            },
        )
    )

    response = gateway.get(LOGIN_PAGE)

    assert response.headers["content-security-policy"] == "frame-ancestors 'self'"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["strict-transport-security"].startswith("max-age=")
    assert response.headers.get_list("referrer-policy") == ["no-referrer"]
    assert "server" not in response.headers


def test_an_oversized_body_is_413_without_reaching_keycloak(
    gateway: TestClient, keycloak: respx.MockRouter
) -> None:
    """Login and token requests are tiny; a huge body is abuse."""
    any_call = keycloak.route().mock(return_value=httpx.Response(200))

    response = gateway.post("/realms/krtr/protocol/openid-connect/token", content=b"x" * 70_000)

    assert response.status_code == 413
    assert not any_call.called


@pytest.mark.parametrize(
    ("raw", "normalized"),
    [
        ("/realms/krtr/", "/realms/krtr/"),
        ("//realms///krtr", "/realms/krtr"),
        ("//admin", "/admin"),
        ("/realms/./krtr/x/..", "/realms/krtr"),
        ("/../../etc/passwd", "/etc/passwd"),
        ("/", "/"),
    ],
)
def test_paths_are_normalized_before_checking_and_forwarding(raw: str, normalized: str) -> None:
    """What is checked is what Keycloak receives; dot segments never climb above the root."""
    assert normalize_path(raw) == normalized
