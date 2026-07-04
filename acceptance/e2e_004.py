"""Step handlers for feature 004 (auth & workspaces) — HTTP + Playwright.

Same binding style as feature 002 (acceptance/e2e_handlers.py), but this
feature's stack needs the dev sign-in enabled, so the module defines its OWN
session-stack fixture (a copy of e2e_base's with ``ANALYST_DEV_LOGIN=1`` in
the API env) instead of editing the shared ``e2e_base.py``. Duplication of
the ~60-line fixture beats touching shared infra (see the 004 plan).

Per-scenario isolation: /api/_reset (which also wipes users/sessions in
fixtures mode), a fresh browser context, and fresh per-user HTTP clients.
"""

from __future__ import annotations

import contextlib
import os
import re
import subprocess
import sys
from typing import Any, Iterator

import httpx
import pytest

from acceptance.e2e_base import (
    _STACK,
    FRONTEND,
    REPO_ROOT,
    ScenarioContext,
    _free_port,
    _wait_http,
    expect_,
    make_registry,
)

step, run_step = make_registry()
_expect = expect_

__all__ = ["ScenarioContext", "run_step", "_e2e_stack", "_e2e_fresh"]

AUTH_ENV_VARS = (
    "ANALYST_DEV_LOGIN",
    "ANALYST_GOOGLE_CLIENT_ID",
    "ANALYST_GOOGLE_CLIENT_SECRET",
    "ANALYST_MICROSOFT_CLIENT_ID",
    "ANALYST_MICROSOFT_CLIENT_SECRET",
)

# Per-scenario state: one cookie-carrying HTTP client per persona, the me
# payload each persona last saw, workspace ids by name, saved cookies.
_CLIENTS: dict[str, httpx.Client] = {}
_ME: dict[str, dict] = {}
_WORKSPACES: dict[str, str] = {}
_SAVED: dict[str, Any] = {}


# --------------------------------------------------------------------------- #
# Session stack — feature-004 copy of e2e_base._e2e_stack + ANALYST_DEV_LOGIN
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="session", autouse=True)
def _e2e_stack():
    from playwright.sync_api import sync_playwright

    api_port, web_port = _free_port(), _free_port()
    api_url = f"http://127.0.0.1:{api_port}"
    web_url = f"http://127.0.0.1:{web_port}"
    procs: list[subprocess.Popen] = []
    try:
        procs.append(
            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "analyst.api.app:app",
                    "--port",
                    str(api_port),
                    "--log-level",
                    "warning",
                ],
                cwd=REPO_ROOT,
                env={**os.environ, "ANALYST_FIXTURES": "1", "ANALYST_DEV_LOGIN": "1"},
            )
        )
        subprocess.run(
            ["bun", "run", "build"],
            cwd=FRONTEND,
            check=True,
            capture_output=True,
            env={**os.environ, "ANALYST_API": api_url},
        )
        procs.append(
            subprocess.Popen(
                [
                    "bun",
                    "run",
                    "preview",
                    "--",
                    "--port",
                    str(web_port),
                    "--strictPort",
                    "--host",
                    "127.0.0.1",
                ],
                cwd=FRONTEND,
                env={**os.environ, "ANALYST_API": api_url},
                stdout=subprocess.DEVNULL,
            )
        )
        _wait_http(f"{api_url}/api/health")
        _wait_http(web_url)

        pw = sync_playwright().start()
        browser = pw.chromium.launch()
        _STACK.update(api=api_url, web=web_url, browser=browser, pw=pw)
        yield
    finally:
        if "browser" in _STACK:
            _STACK["browser"].close()
        if "pw" in _STACK:
            _STACK["pw"].stop()
        for proc in procs:
            proc.terminate()
        for proc in procs:
            proc.wait(timeout=10)
        _STACK.clear()


@pytest.fixture(autouse=True)
def _e2e_fresh():
    """Per-scenario isolation: reset (repos + users/sessions), fresh context."""
    httpx.post(f"{_STACK['api']}/api/_reset", timeout=10.0)
    context = _STACK["browser"].new_context()
    _STACK["page"] = context.new_page()
    yield
    context.close()
    _STACK.pop("page", None)
    for client in _CLIENTS.values():
        client.close()
    _CLIENTS.clear()
    _ME.clear()
    _WORKSPACES.clear()
    _SAVED.clear()


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _client(ctx: ScenarioContext, name: str) -> httpx.Client:
    if name not in _CLIENTS:
        _CLIENTS[name] = httpx.Client(base_url=ctx.api, timeout=10.0)
    return _CLIENTS[name]


def _dev_email(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", ".", name.strip().lower()).strip(".")
    return f"{slug}@dev.local"


def _sign_in(ctx: ScenarioContext, name: str) -> dict:
    response = _client(ctx, name).post("/api/auth/dev-login", json={"name": name})
    assert response.status_code == 200, f"dev-login failed: {response.text}"
    me = response.json()
    _ME[name] = me
    for workspace in me["workspaces"]:
        _WORKSPACES.setdefault(workspace["name"], workspace["id"])
    return me


def _switch(ctx: ScenarioContext, name: str, workspace: str) -> None:
    response = _client(ctx, name).post(
        "/api/auth/workspace", json={"workspaceId": _WORKSPACES[workspace]}
    )
    assert response.status_code == 200, f"switch failed: {response.text}"
    _ME[name] = response.json()


@contextlib.contextmanager
def _without_auth_env() -> Iterator[None]:
    saved = {k: os.environ.pop(k) for k in AUTH_ENV_VARS if k in os.environ}
    try:
        yield
    finally:
        os.environ.update(saved)


# --------------------------------------------------------------------------- #
# API-contract steps (AC-1..AC-8)
# --------------------------------------------------------------------------- #
@step(r"the analyst service is running with dev sign-in enabled")
def given_service_with_dev_login(ctx: ScenarioContext) -> None:
    health = httpx.get(f"{ctx.api}/api/health").json()
    assert health["ok"] is True and health["fixtures"] is True
    providers = httpx.get(f"{ctx.api}/api/auth/providers").json()
    assert providers["devLogin"] is True, "stack must run with ANALYST_DEV_LOGIN=1"


@step(r"a client asks which sign-in methods are available")
def when_ask_providers(ctx: ScenarioContext) -> None:
    ctx.data = httpx.get(f"{ctx.api}/api/auth/providers").json()


@step(r"dev sign-in is offered")
def then_dev_login_offered(ctx: ScenarioContext) -> None:
    assert ctx.data["authEnabled"] is True and ctx.data["devLogin"] is True


@step(r"Google and Microsoft sign-in are reported as not configured")
def then_oauth_unconfigured(ctx: ScenarioContext) -> None:
    assert ctx.data["google"] is False and ctx.data["microsoft"] is False


@step(r"a signed-out client lists the datasets")
def when_anonymous_lists_datasets(ctx: ScenarioContext) -> None:
    ctx.response = httpx.get(f"{ctx.api}/api/datasets")


@step(r"the request is rejected as unauthenticated")
def then_unauthenticated(ctx: ScenarioContext) -> None:
    assert ctx.response is not None and ctx.response.status_code == 401


@step(r"a signed-out client checks the service health")
def when_anonymous_checks_health(ctx: ScenarioContext) -> None:
    ctx.response = httpx.get(f"{ctx.api}/api/health")
    ctx.data = ctx.response.json()


@step(r"the service answers that it is healthy")
def then_healthy(ctx: ScenarioContext) -> None:
    assert ctx.response is not None and ctx.response.status_code == 200
    assert ctx.data["ok"] is True


@step(r'"(?P<name>[^"]+)" signs in for the first time')
@step(r'"(?P<name>[^"]+)" has signed in as the first user')
def when_user_signs_in(ctx: ScenarioContext, name: str) -> None:
    _sign_in(ctx, name)


@step(r'"(?P<name>[^"]+)" is an admin with a default workspace')
def then_user_is_admin(ctx: ScenarioContext, name: str) -> None:
    me = _ME[name]
    assert me["user"]["isAdmin"] is True, f"{name} should be admin"
    names = [w["name"] for w in me["workspaces"]]
    assert names == ["Default"], f"expected a default workspace, got {names}"
    assert me["activeWorkspaceId"] == me["workspaces"][0]["id"]


@step(r'"(?P<name>[^"]+)" is not an admin and belongs to no workspace')
def then_user_is_plain(ctx: ScenarioContext, name: str) -> None:
    me = _ME[name]
    assert me["user"]["isAdmin"] is False, f"{name} should not be admin"
    assert me["workspaces"] == [] and me["activeWorkspaceId"] is None


@step(r'"(?P<name>[^"]+)" creates the workspace "(?P<workspace>[^"]+)"')
def when_create_workspace(ctx: ScenarioContext, name: str, workspace: str) -> None:
    response = _client(ctx, name).post("/api/workspaces", json={"name": workspace})
    assert response.status_code == 201, f"create failed: {response.text}"
    _WORKSPACES[workspace] = response.json()["id"]


@step(
    r'"(?P<name>[^"]+)" adds "(?P<member>[^"]+)" as a member of "(?P<workspace>[^"]+)"'
)
def when_add_member(
    ctx: ScenarioContext, name: str, member: str, workspace: str
) -> None:
    response = _client(ctx, name).post(
        f"/api/workspaces/{_WORKSPACES[workspace]}/members",
        json={"email": _dev_email(member), "name": member},
    )
    assert response.status_code == 201, f"add member failed: {response.text}"


@step(r'"(?P<name>[^"]+)" sees the workspace "(?P<workspace>[^"]+)" after signing in')
def then_member_sees_workspace(ctx: ScenarioContext, name: str, workspace: str) -> None:
    me = _sign_in(ctx, name)
    assert workspace in [w["name"] for w in me["workspaces"]]


@step(r'"(?P<name>[^"]+)" cannot create workspaces')
def then_cannot_create_workspace(ctx: ScenarioContext, name: str) -> None:
    response = _client(ctx, name).post("/api/workspaces", json={"name": "Rogue"})
    assert response.status_code == 403, f"expected 403, got {response.status_code}"


@step(
    r'"(?P<name>[^"]+)" has created and switched to the workspace "(?P<workspace>[^"]+)"'
)
def given_created_and_switched(ctx: ScenarioContext, name: str, workspace: str) -> None:
    when_create_workspace(ctx, name, workspace)
    _switch(ctx, name, workspace)


@step(r'"(?P<name>[^"]+)" deletes the dataset "(?P<dataset>[^"]+)"')
def when_delete_dataset(ctx: ScenarioContext, name: str, dataset: str) -> None:
    assert _client(ctx, name).delete(f"/api/datasets/{dataset}").status_code == 204


@step(r'"(?P<name>[^"]+)" switches back to her default workspace')
def when_switch_to_default(ctx: ScenarioContext, name: str) -> None:
    _switch(ctx, name, "Default")


@step(r'the dataset "(?P<dataset>[^"]+)" is still present')
def then_dataset_present(ctx: ScenarioContext, dataset: str) -> None:
    client = _CLIENTS["Ana"]
    assert client.get(f"/api/datasets/{dataset}").status_code == 200


@step(r'the workspace "(?P<workspace>[^"]+)" no longer contains "(?P<dataset>[^"]+)"')
def then_workspace_lacks_dataset(
    ctx: ScenarioContext, workspace: str, dataset: str
) -> None:
    _switch(ctx, "Ana", workspace)
    assert _CLIENTS["Ana"].get(f"/api/datasets/{dataset}").status_code == 404


@step(r'"(?P<name>[^"]+)" signs out')
def when_sign_out(ctx: ScenarioContext, name: str) -> None:
    client = _client(ctx, name)
    _SAVED["cookie"] = dict(client.cookies)
    assert client.post("/api/auth/logout").status_code == 204


@step(r"her previous session can no longer list the datasets")
def then_old_session_dead(ctx: ScenarioContext) -> None:
    response = httpx.get(f"{ctx.api}/api/datasets", cookies=_SAVED["cookie"])
    assert response.status_code == 401


@step(r"a client starts a Google sign-in")
def when_start_google_login(ctx: ScenarioContext) -> None:
    ctx.response = httpx.get(f"{ctx.api}/api/auth/login/google")


@step(r"the sign-in is refused because Google is not configured")
def then_google_refused(ctx: ScenarioContext) -> None:
    assert ctx.response is not None and ctx.response.status_code == 400
    assert "not configured" in ctx.response.json()["detail"]


@step(r"an analyst service with no sign-in method configured")
def given_unconfigured_service(ctx: ScenarioContext) -> None:
    from fastapi.testclient import TestClient

    from analyst.api.app import create_app
    from analyst.api.repository import FixtureRepository

    with _without_auth_env():
        _SAVED["plain_client"] = TestClient(create_app(FixtureRepository()))


@step(r"a client lists the datasets without signing in")
def when_plain_list_datasets(ctx: ScenarioContext) -> None:
    with _without_auth_env():
        response = _SAVED["plain_client"].get("/api/datasets")
    assert response.status_code == 200, f"expected open API, got {response.status_code}"
    ctx.data = response.json()


@step(r"the datasets are served normally")
def then_datasets_served(ctx: ScenarioContext) -> None:
    assert {d["name"] for d in ctx.data} == {"sales", "customers", "products"}


# --------------------------------------------------------------------------- #
# Frontend-flow steps (AC-9..AC-13)
# --------------------------------------------------------------------------- #
@step(r"the analyst app is open in a browser")
def given_app_open(ctx: ScenarioContext) -> None:
    ctx.page.goto(_STACK["web"])


@step(r"the sign-in page is shown")
def then_login_page_shown(ctx: ScenarioContext) -> None:
    heading = ctx.page.get_by_role("heading", name="Sign in to analyst")
    _expect()(heading).to_be_visible()


@step(r'the visitor signs in as "(?P<name>[^"]+)"')
def when_visitor_signs_in(ctx: ScenarioContext, name: str) -> None:
    ctx.page.get_by_label("Your name").fill(name)
    ctx.page.get_by_role("button", name="Continue", exact=True).click()


@step(r'the workspace app appears with "(?P<name>[^"]+)" shown in the header')
def then_app_with_user(ctx: ScenarioContext, name: str) -> None:
    expect = _expect()
    expect(ctx.page.get_by_text("Semantic catalog").first).to_be_visible()
    expect(ctx.page.get_by_text(name, exact=True).first).to_be_visible()


@step(r"the sign-in page says (?P<provider>Google|Microsoft) sign-in is not configured")
def then_login_page_says_unconfigured(ctx: ScenarioContext, provider: str) -> None:
    message = f"{provider} sign-in is not configured"
    _expect()(ctx.page.get_by_text(message)).to_be_visible()


@step(r'"(?P<name>[^"]+)" is signed in to the app')
def given_signed_in_app(ctx: ScenarioContext, name: str) -> None:
    given_app_open(ctx)
    then_login_page_shown(ctx)
    when_visitor_signs_in(ctx, name)
    _expect()(ctx.page.get_by_text("Semantic catalog").first).to_be_visible()


@step(r'she deletes the dataset "(?P<dataset>[^"]+)"')
def when_ui_delete_dataset(ctx: ScenarioContext, dataset: str) -> None:
    ctx.page.get_by_role("button", name=f"Delete dataset {dataset}").click()
    ctx.page.get_by_role("button", name=f"Confirm delete {dataset}").click()
    _expect()(ctx.page.get_by_text(f"{dataset}.csv")).to_have_count(0)


@step(r'she creates and switches to the workspace "(?P<workspace>[^"]+)"')
def when_ui_create_workspace(ctx: ScenarioContext, workspace: str) -> None:
    expect = _expect()
    ctx.page.get_by_role("button", name="New workspace").click()
    ctx.page.get_by_label("New workspace name").fill(workspace)
    ctx.page.get_by_role("button", name="Create workspace").click()
    # creation switches to the new workspace; the switcher shows it selected
    expect(ctx.page.get_by_label("Switch workspace")).to_be_visible()
    expect(ctx.page.get_by_role("button", name="Create workspace")).to_have_count(0)


@step(r'the semantic catalog lists "(?P<file_name>[^"]+)"')
def then_catalog_lists(ctx: ScenarioContext, file_name: str) -> None:
    _expect()(ctx.page.get_by_text(file_name).first).to_be_visible()


@step(r"she switches to her default workspace")
def when_ui_switch_default(ctx: ScenarioContext) -> None:
    ctx.page.get_by_label("Switch workspace").select_option(label="Default")


@step(r'"(?P<file_name>[^"]+)" is absent from the semantic catalog')
def then_catalog_lacks(ctx: ScenarioContext, file_name: str) -> None:
    expect = _expect()
    # anchor on another seeded dataset so we know the catalog has loaded
    expect(ctx.page.get_by_text("customers.csv").first).to_be_visible()
    expect(ctx.page.get_by_text(file_name)).to_have_count(0)


@step(r"she signs out")
def when_ui_sign_out(ctx: ScenarioContext) -> None:
    ctx.page.get_by_role("button", name="Sign out").click()


@step(r"a notice explains that no workspace has been assigned yet")
def then_no_workspace_notice(ctx: ScenarioContext) -> None:
    _expect()(
        ctx.page.get_by_text("No workspace has been assigned", exact=False)
    ).to_be_visible()
