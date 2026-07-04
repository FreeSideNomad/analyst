"""Auth & workspace API tests (feature 004) — via FastAPI TestClient.

Covers: opt-in enforcement (backward compat), provider discovery, dev
sign-in (first user = admin + default workspace), workspace management &
isolation, logout revocation, and the OAuth redirect/callback flow against
the ``_exchange_code`` seam (no network, no real credentials).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from analyst.api.app import create_app
from analyst.api.repository import FixtureRepository
from analyst.api.routes import auth as auth_mod

AUTH_ENV = (
    "ANALYST_DEV_LOGIN",
    "ANALYST_GOOGLE_CLIENT_ID",
    "ANALYST_GOOGLE_CLIENT_SECRET",
    "ANALYST_MICROSOFT_CLIENT_ID",
    "ANALYST_MICROSOFT_CLIENT_SECRET",
    "ANALYST_SESSION_SECRET",
)


@pytest.fixture(autouse=True)
def _clean_auth_env(monkeypatch):
    for var in AUTH_ENV:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("ANALYST_FIXTURES", "1")


def make_client() -> TestClient:
    return TestClient(create_app(FixtureRepository()))


def dev_client(monkeypatch) -> TestClient:
    monkeypatch.setenv("ANALYST_DEV_LOGIN", "1")
    return make_client()


def login(client: TestClient, name: str) -> dict:
    response = client.post("/api/auth/dev-login", json={"name": name})
    assert response.status_code == 200, response.text
    return response.json()


# --------------------------------------------------------------------------- #
# AC-8 — backward compat: no login method configured -> API open, as before
# --------------------------------------------------------------------------- #
def test_without_configuration_the_api_is_open(monkeypatch):
    monkeypatch.delenv("ANALYST_DEV_LOGIN", raising=False)
    client = make_client()
    assert auth_mod.auth_enabled() is False
    assert client.get("/api/datasets").status_code == 200
    assert client.get("/api/health").json()["ok"] is True
    body = client.get("/api/auth/providers").json()
    assert body == {
        "authEnabled": False,
        "devLogin": False,
        "google": False,
        "microsoft": False,
    }


def test_without_configuration_dev_login_is_refused():
    client = make_client()
    assert client.post("/api/auth/dev-login", json={"name": "Ana"}).status_code == 403


# --------------------------------------------------------------------------- #
# AC-1 — provider discovery
# --------------------------------------------------------------------------- #
def test_providers_report_dev_login_and_unconfigured_oauth(monkeypatch):
    client = dev_client(monkeypatch)
    body = client.get("/api/auth/providers").json()
    assert body["authEnabled"] is True and body["devLogin"] is True
    assert body["google"] is False and body["microsoft"] is False


def test_configured_oauth_flips_discovery_and_enables_auth(monkeypatch):
    monkeypatch.setenv("ANALYST_GOOGLE_CLIENT_ID", "gid")
    monkeypatch.setenv("ANALYST_GOOGLE_CLIENT_SECRET", "gsecret")
    body = make_client().get("/api/auth/providers").json()
    assert body["authEnabled"] is True and body["google"] is True
    assert body["devLogin"] is False


# --------------------------------------------------------------------------- #
# AC-2 — session enforcement once a login method is configured
# --------------------------------------------------------------------------- #
def test_protected_routes_require_a_session(monkeypatch):
    client = dev_client(monkeypatch)
    assert client.get("/api/datasets").status_code == 401
    assert client.get("/api/catalog").status_code == 401
    assert client.post("/api/query", json={"question": "hi"}).status_code == 401
    # open endpoints stay open
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/auth/providers").status_code == 200
    assert client.get("/api/auth/me").status_code == 401  # self-guarded


def test_reset_stays_open_in_fixtures_mode(monkeypatch):
    client = dev_client(monkeypatch)
    assert client.post("/api/_reset").status_code == 204


def test_a_forged_cookie_is_rejected(monkeypatch):
    client = dev_client(monkeypatch)
    client.cookies.set(auth_mod.SESSION_COOKIE, "forged.deadbeef")
    assert client.get("/api/datasets").status_code == 401


# --------------------------------------------------------------------------- #
# AC-3 — first user becomes admin with a default workspace
# --------------------------------------------------------------------------- #
def test_first_dev_login_is_admin_with_default_workspace(monkeypatch):
    client = dev_client(monkeypatch)
    me = login(client, "Ana")
    assert me["user"]["isAdmin"] is True
    assert [w["name"] for w in me["workspaces"]] == ["Default"]
    assert me["activeWorkspaceId"] == me["workspaces"][0]["id"]
    # authenticated requests now succeed
    assert client.get("/api/datasets").status_code == 200


def test_second_user_is_not_admin_and_has_no_workspace(monkeypatch):
    monkeypatch.setenv("ANALYST_DEV_LOGIN", "1")
    admin = make_client()
    app = admin.app  # share one app (one AppState) across both clients
    login(admin, "Ana")
    ben = TestClient(app)
    me = login(ben, "Ben")
    assert me["user"]["isAdmin"] is False and me["workspaces"] == []
    assert me["activeWorkspaceId"] is None
    # no workspace -> workspace data is refused with a clear message
    response = ben.get("/api/datasets")
    assert response.status_code == 403
    assert "workspace" in response.json()["detail"].lower()


# --------------------------------------------------------------------------- #
# AC-4 — admin manages workspaces & members; non-admins cannot
# --------------------------------------------------------------------------- #
def test_admin_creates_workspace_and_adds_member(monkeypatch):
    monkeypatch.setenv("ANALYST_DEV_LOGIN", "1")
    admin = make_client()
    app = admin.app
    login(admin, "Ana")
    created = admin.post("/api/workspaces", json={"name": "Finance"})
    assert created.status_code == 201
    ws_id = created.json()["id"]
    added = admin.post(
        f"/api/workspaces/{ws_id}/members", json={"email": "ben@dev.local"}
    )
    assert added.status_code == 201
    members = admin.get(f"/api/workspaces/{ws_id}/members").json()
    assert {m["email"] for m in members} == {"ana@dev.local", "ben@dev.local"}
    # Ben signs in later and sees Finance
    ben = TestClient(app)
    me = login(ben, "Ben")
    assert [w["name"] for w in me["workspaces"]] == ["Finance"]


def test_non_admin_cannot_create_workspaces_or_add_members(monkeypatch):
    monkeypatch.setenv("ANALYST_DEV_LOGIN", "1")
    admin = make_client()
    app = admin.app
    login(admin, "Ana")
    ws_id = admin.post("/api/workspaces", json={"name": "Finance"}).json()["id"]
    ben = TestClient(app)
    login(ben, "Ben")
    assert ben.post("/api/workspaces", json={"name": "Rogue"}).status_code == 403
    assert (
        ben.post(f"/api/workspaces/{ws_id}/members", json={"email": "x@y.z"})
    ).status_code == 403


# --------------------------------------------------------------------------- #
# AC-5 — per-workspace dataset isolation
# --------------------------------------------------------------------------- #
def test_datasets_are_isolated_per_workspace(monkeypatch):
    client = dev_client(monkeypatch)
    me = login(client, "Ana")
    default_id = me["activeWorkspaceId"]
    finance_id = client.post("/api/workspaces", json={"name": "Finance"}).json()["id"]
    client.post("/api/auth/workspace", json={"workspaceId": finance_id})
    assert client.delete("/api/datasets/sales").status_code == 204
    assert client.get("/api/datasets/sales").status_code == 404
    # back to the default workspace: sales is untouched
    client.post("/api/auth/workspace", json={"workspaceId": default_id})
    assert client.get("/api/datasets/sales").status_code == 200


def test_switching_to_a_foreign_workspace_is_refused(monkeypatch):
    monkeypatch.setenv("ANALYST_DEV_LOGIN", "1")
    admin = make_client()
    app = admin.app
    me = login(admin, "Ana")
    default_id = me["activeWorkspaceId"]
    ben = TestClient(app)
    login(ben, "Ben")
    response = ben.post("/api/auth/workspace", json={"workspaceId": default_id})
    assert response.status_code == 403


# --------------------------------------------------------------------------- #
# AC-6 — logout revokes the session server-side
# --------------------------------------------------------------------------- #
def test_logout_revokes_the_session(monkeypatch):
    client = dev_client(monkeypatch)
    login(client, "Ana")
    cookie = client.cookies.get(auth_mod.SESSION_COOKIE)
    assert client.post("/api/auth/logout").status_code == 204
    # even replaying the OLD cookie fails — the row is gone
    replay = TestClient(client.app)
    replay.cookies.set(auth_mod.SESSION_COOKIE, cookie)
    assert replay.get("/api/datasets").status_code == 401


# --------------------------------------------------------------------------- #
# AC-7 + OAuth flow — redirect & callback against the _exchange_code seam
# --------------------------------------------------------------------------- #
def test_unconfigured_provider_login_is_refused_clearly(monkeypatch):
    client = dev_client(monkeypatch)
    response = client.get("/api/auth/login/google", follow_redirects=False)
    assert response.status_code == 400
    assert "not configured" in response.json()["detail"]
    assert client.get("/api/auth/login/nope").status_code == 404


def test_google_login_redirects_to_google(monkeypatch):
    monkeypatch.setenv("ANALYST_GOOGLE_CLIENT_ID", "gid")
    monkeypatch.setenv("ANALYST_GOOGLE_CLIENT_SECRET", "gsecret")
    response = make_client().get("/api/auth/login/google", follow_redirects=False)
    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "client_id=gid" in location and "state=" in location
    assert "callback%2Fgoogle" in location


def test_microsoft_login_redirects_to_microsoft(monkeypatch):
    monkeypatch.setenv("ANALYST_MICROSOFT_CLIENT_ID", "mid")
    monkeypatch.setenv("ANALYST_MICROSOFT_CLIENT_SECRET", "msecret")
    response = make_client().get("/api/auth/login/microsoft", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"].startswith(
        "https://login.microsoftonline.com/common/oauth2/v2.0/authorize?"
    )


def test_oauth_callback_signs_the_user_in(monkeypatch):
    monkeypatch.setenv("ANALYST_GOOGLE_CLIENT_ID", "gid")
    monkeypatch.setenv("ANALYST_GOOGLE_CLIENT_SECRET", "gsecret")
    monkeypatch.setattr(
        auth_mod,
        "_exchange_code",
        lambda cfg, code, uri: {"email": "ana@example.com", "name": "Ana"},
    )
    client = make_client()
    start = client.get("/api/auth/login/google", follow_redirects=False)
    state = start.headers["location"].split("state=")[1].split("&")[0]
    import urllib.parse

    state = urllib.parse.unquote(state)
    response = client.get(
        f"/api/auth/callback/google?code=abc&state={urllib.parse.quote(state)}",
        follow_redirects=False,
    )
    assert response.status_code == 302 and response.headers["location"] == "/"
    me = client.get("/api/auth/me").json()
    assert me["user"]["email"] == "ana@example.com"
    assert me["user"]["isAdmin"] is True  # first user, via OAuth too
    assert [w["name"] for w in me["workspaces"]] == ["Default"]


def test_oauth_callback_rejects_a_bad_state(monkeypatch):
    monkeypatch.setenv("ANALYST_GOOGLE_CLIENT_ID", "gid")
    monkeypatch.setenv("ANALYST_GOOGLE_CLIENT_SECRET", "gsecret")
    client = make_client()
    response = client.get(
        "/api/auth/callback/google?code=abc&state=forged.sig",
        follow_redirects=False,
    )
    assert response.status_code == 400


# --------------------------------------------------------------------------- #
# Reset clears auth state (fixtures mode) — first-user semantics repeat
# --------------------------------------------------------------------------- #
def test_reset_clears_users_and_sessions(monkeypatch):
    client = dev_client(monkeypatch)
    login(client, "Ana")
    assert client.post("/api/_reset").status_code == 204
    assert client.get("/api/datasets").status_code == 401  # session revoked
    me = login(client, "Zoe")  # first user again after reset
    assert me["user"]["isAdmin"] is True
