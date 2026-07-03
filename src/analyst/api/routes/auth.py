"""Auth & workspace routes + session middleware (feature 004).

Auth is OPT-IN by configuration: with no login method configured (no OAuth
client env vars and ``ANALYST_DEV_LOGIN`` unset) the middleware passes every
request through and the API behaves exactly as before this feature. As soon
as any method is configured, ``/api/*`` requires a session — except
``/api/health``, ``/api/auth/*`` and (fixtures mode only) ``/api/_reset``.

Sessions are server-side SQLite rows (``analyst.persistence``) referenced by
an HMAC-signed, HTTP-only cookie. OAuth (Google + Microsoft) runs the
authorization-code flow; real client credentials are env-configured — see
features/004-auth-workspaces/runbook.md.
"""

from __future__ import annotations

import os
import re
import secrets
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx
from fastapi import APIRouter, FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse

from analyst.api.schemas import Camel
from analyst.persistence import AppState, SessionRecord, sign, unsign
from analyst.persistence.appstate import SESSION_TTL_SECONDS

SESSION_COOKIE = "analyst_session"
_STATE_MAX_AGE = 600.0  # seconds an OAuth state token stays valid

router = APIRouter(prefix="/api/auth")
workspaces_router = APIRouter(prefix="/api/workspaces")


# --------------------------------------------------------------------------- #
# Configuration (read from env at request time — nothing cached at import)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class OAuthProvider:
    key: str  # "google" | "microsoft"
    title: str
    authorize_url: str
    token_url: str
    userinfo_url: str
    scope: str
    client_id: str
    client_secret: str


def dev_login_enabled() -> bool:
    return os.environ.get("ANALYST_DEV_LOGIN", "0") == "1"


def _oauth_provider(key: str) -> OAuthProvider | None:
    """The configured provider, or None when its env vars are absent."""
    if key == "google":
        client_id = os.environ.get("ANALYST_GOOGLE_CLIENT_ID", "")
        client_secret = os.environ.get("ANALYST_GOOGLE_CLIENT_SECRET", "")
        if not (client_id and client_secret):
            return None
        return OAuthProvider(
            key="google",
            title="Google",
            authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
            token_url="https://oauth2.googleapis.com/token",
            userinfo_url="https://openidconnect.googleapis.com/v1/userinfo",
            scope="openid email profile",
            client_id=client_id,
            client_secret=client_secret,
        )
    if key == "microsoft":
        client_id = os.environ.get("ANALYST_MICROSOFT_CLIENT_ID", "")
        client_secret = os.environ.get("ANALYST_MICROSOFT_CLIENT_SECRET", "")
        if not (client_id and client_secret):
            return None
        tenant = os.environ.get("ANALYST_MICROSOFT_TENANT", "common")
        base = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0"
        return OAuthProvider(
            key="microsoft",
            title="Microsoft",
            authorize_url=f"{base}/authorize",
            token_url=f"{base}/token",
            userinfo_url="https://graph.microsoft.com/oidc/userinfo",
            scope="openid email profile",
            client_id=client_id,
            client_secret=client_secret,
        )
    return None


def auth_enabled() -> bool:
    """Any login method configured? Backward compat hinges on this being
    False in an unconfigured environment (features 001/002 stay untouched)."""
    return (
        dev_login_enabled()
        or _oauth_provider("google") is not None
        or _oauth_provider("microsoft") is not None
    )


_PROCESS_SECRET: str | None = None


def _secret() -> str:
    """HMAC key: ANALYST_SESSION_SECRET, else a per-process random (dev)."""
    configured = os.environ.get("ANALYST_SESSION_SECRET")
    if configured:
        return configured
    global _PROCESS_SECRET
    if _PROCESS_SECRET is None:
        _PROCESS_SECRET = secrets.token_hex(32)
    return _PROCESS_SECRET


# --------------------------------------------------------------------------- #
# App-state holder (lazy; reset between e2e scenarios via reset_state)
# --------------------------------------------------------------------------- #
def app_state(app: FastAPI) -> AppState:
    holder = getattr(app.state, "auth_holder", None)
    if holder is None:
        from analyst.api.app import fixtures_enabled

        if fixtures_enabled():
            path: str | Path = ":memory:"
        else:
            data_dir = os.environ.get("ANALYST_DATA_DIR", ".analyst-data")
            path = Path(data_dir) / "app.sqlite3"
        holder = {"state": AppState(path)}
        app.state.auth_holder = holder
    state: AppState = holder["state"]
    return state


def reset_state(app: FastAPI) -> None:
    """Test-only (fixtures reset): drop users/workspaces/sessions."""
    holder = getattr(app.state, "auth_holder", None)
    if holder is not None:
        holder["state"].close()
        app.state.auth_holder = None


# --------------------------------------------------------------------------- #
# Sessions — signed cookie -> SQLite row
# --------------------------------------------------------------------------- #
def resolve_session(request: Request) -> SessionRecord | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    session_id = unsign(token, _secret())
    if session_id is None:
        return None
    return app_state(request.app).get_session(session_id)


def _set_session_cookie(response: Response, session_id: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        sign(session_id, _secret()),
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        samesite="lax",
        path="/",
    )


def require_session(request: Request) -> SessionRecord:
    session = getattr(request.state, "auth_session", None) or resolve_session(request)
    if session is None:
        raise HTTPException(401, "Not authenticated")
    return session


def _require_admin(request: Request) -> SessionRecord:
    session = require_session(request)
    user = app_state(request.app).user_by_id(session.user_id)
    if user is None or not user.is_admin:
        raise HTTPException(403, "Only the admin can do this")
    return session


# --------------------------------------------------------------------------- #
# Middleware — session enforcement (no-op while auth is not configured)
# --------------------------------------------------------------------------- #
def install(app: FastAPI) -> None:
    @app.middleware("http")
    async def _session_guard(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        path = request.url.path
        if not path.startswith("/api") or not auth_enabled():
            return await call_next(request)
        if path == "/api/health" or path.startswith("/api/auth/"):
            return await call_next(request)
        if path == "/api/_reset":
            from analyst.api.app import fixtures_enabled

            if fixtures_enabled():
                return await call_next(request)
        session = resolve_session(request)
        if session is None:
            return JSONResponse(
                status_code=401, content={"detail": "Not authenticated"}
            )
        request.state.auth_session = session
        return await call_next(request)


# --------------------------------------------------------------------------- #
# Wire schemas (auth-only; kept here so api/schemas.py stays untouched)
# --------------------------------------------------------------------------- #
class DevLoginRequest(Camel):
    name: str


class SwitchWorkspaceRequest(Camel):
    workspace_id: str


class CreateWorkspaceRequest(Camel):
    name: str


class AddMemberRequest(Camel):
    email: str
    name: str = ""


def _me_payload(state: AppState, session: SessionRecord) -> dict[str, Any]:
    user = state.user_by_id(session.user_id)
    if user is None:  # pragma: no cover - session rows reference users
        raise HTTPException(401, "Not authenticated")
    return {
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "isAdmin": user.is_admin,
        },
        "workspaces": [
            {"id": w.id, "name": w.name} for w in state.workspaces_for(user.id)
        ],
        "activeWorkspaceId": session.workspace_id,
    }


# --------------------------------------------------------------------------- #
# Auth routes
# --------------------------------------------------------------------------- #
@router.get("/providers")
def providers() -> dict[str, bool]:
    return {
        "authEnabled": auth_enabled(),
        "devLogin": dev_login_enabled(),
        "google": _oauth_provider("google") is not None,
        "microsoft": _oauth_provider("microsoft") is not None,
    }


def _dev_email(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", ".", name.strip().lower()).strip(".")
    return f"{slug or 'user'}@dev.local"


@router.post("/dev-login")
def dev_login(body: DevLoginRequest, request: Request, response: Response) -> dict:
    if not dev_login_enabled():
        raise HTTPException(403, "Dev sign-in is not enabled")
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "A name is required")
    state = app_state(request.app)
    user = state.sign_in(_dev_email(name), name, "dev")
    session = state.create_session(user.id)
    _set_session_cookie(response, session.id)
    return _me_payload(state, session)


@router.get("/me")
def me(request: Request) -> dict:
    session = require_session(request)
    return _me_payload(app_state(request.app), session)


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response) -> None:
    session = resolve_session(request)
    if session is not None:
        app_state(request.app).delete_session(session.id)
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.post("/workspace")
def switch_workspace(body: SwitchWorkspaceRequest, request: Request) -> dict:
    session = require_session(request)
    state = app_state(request.app)
    if not state.is_member(session.user_id, body.workspace_id):
        raise HTTPException(403, "You are not a member of that workspace")
    state.set_active_workspace(session.id, body.workspace_id)
    refreshed = state.get_session(session.id)
    assert refreshed is not None
    return _me_payload(state, refreshed)


# --------------------------------------------------------------------------- #
# OAuth — authorization-code flow (Google + Microsoft)
# --------------------------------------------------------------------------- #
def _public_base(request: Request) -> str:
    configured = os.environ.get("ANALYST_PUBLIC_URL")
    return (configured or str(request.base_url)).rstrip("/")


def _redirect_uri(request: Request, provider: str) -> str:
    return f"{_public_base(request)}/api/auth/callback/{provider}"


def _provider_or_reject(key: str) -> OAuthProvider:
    if key not in ("google", "microsoft"):
        raise HTTPException(404, f"Unknown sign-in provider '{key}'")
    provider = _oauth_provider(key)
    if provider is None:
        raise HTTPException(400, f"{key.capitalize()} sign-in is not configured")
    return provider


@router.get("/login/{provider}")
def oauth_login(provider: str, request: Request) -> RedirectResponse:
    cfg = _provider_or_reject(provider)
    state_token = sign(f"{secrets.token_urlsafe(16)}:{int(time.time())}", _secret())
    params = {
        "client_id": cfg.client_id,
        "redirect_uri": _redirect_uri(request, cfg.key),
        "response_type": "code",
        "scope": cfg.scope,
        "state": state_token,
    }
    url = f"{cfg.authorize_url}?{urllib.parse.urlencode(params)}"
    return RedirectResponse(url, status_code=302)


def _check_state(state_token: str | None) -> None:
    value = unsign(state_token or "", _secret())
    if value is None:
        raise HTTPException(400, "Invalid sign-in state — please retry")
    _, _, issued = value.rpartition(":")
    if not issued.isdigit() or time.time() - int(issued) > _STATE_MAX_AGE:
        raise HTTPException(400, "The sign-in attempt expired — please retry")


def _exchange_code(cfg: OAuthProvider, code: str, redirect_uri: str) -> dict:
    """Code -> tokens -> userinfo. Returns at least {'email', 'name'}.

    Seam for tests: unit tests monkeypatch this; e2e uses dev sign-in.
    """
    with httpx.Client(timeout=15.0) as client:
        token_response = client.post(
            cfg.token_url,
            data={
                "client_id": cfg.client_id,
                "client_secret": cfg.client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
        )
        if token_response.status_code != 200:
            raise HTTPException(502, f"{cfg.title} token exchange failed")
        access_token = token_response.json().get("access_token")
        if not access_token:
            raise HTTPException(502, f"{cfg.title} returned no access token")
        userinfo = client.get(
            cfg.userinfo_url,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if userinfo.status_code != 200:
            raise HTTPException(502, f"{cfg.title} userinfo lookup failed")
        return dict(userinfo.json())


@router.get("/callback/{provider}")
def oauth_callback(
    provider: str,
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    cfg = _provider_or_reject(provider)
    if error:
        raise HTTPException(400, f"{cfg.title} sign-in was refused: {error}")
    if not code:
        raise HTTPException(400, f"{cfg.title} sign-in returned no code")
    _check_state(state)
    profile = _exchange_code(cfg, code, _redirect_uri(request, cfg.key))
    email = profile.get("email") or profile.get("preferred_username")
    if not email:
        raise HTTPException(502, f"{cfg.title} returned no e-mail address")
    name = profile.get("name") or str(email).split("@")[0]
    app = app_state(request.app)
    user = app.sign_in(str(email), str(name), cfg.key)
    session = app.create_session(user.id)
    response = RedirectResponse("/", status_code=302)
    _set_session_cookie(response, session.id)
    return response


# --------------------------------------------------------------------------- #
# Workspace management (admin) — guarded by the middleware + role checks
# --------------------------------------------------------------------------- #
@workspaces_router.post("", status_code=201)
def create_workspace(body: CreateWorkspaceRequest, request: Request) -> dict:
    session = _require_admin(request)
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "A workspace name is required")
    workspace = app_state(request.app).create_workspace(name, session.user_id)
    return {"id": workspace.id, "name": workspace.name}


@workspaces_router.get("/{workspace_id}/members")
def list_members(workspace_id: str, request: Request) -> list[dict]:
    session = require_session(request)
    state = app_state(request.app)
    user = state.user_by_id(session.user_id)
    if user is None or not (user.is_admin or state.is_member(user.id, workspace_id)):
        raise HTTPException(403, "You are not a member of that workspace")
    if state.workspace_by_id(workspace_id) is None:
        raise HTTPException(404, "Workspace not found")
    return [
        {"id": u.id, "name": u.name, "email": u.email, "isAdmin": u.is_admin}
        for u in state.members_of(workspace_id)
    ]


@workspaces_router.post("/{workspace_id}/members", status_code=201)
def add_member(workspace_id: str, body: AddMemberRequest, request: Request) -> dict:
    _require_admin(request)
    state = app_state(request.app)
    if state.workspace_by_id(workspace_id) is None:
        raise HTTPException(404, "Workspace not found")
    email = body.email.strip()
    if not email or "@" not in email:
        raise HTTPException(400, "A valid e-mail address is required")
    membership = state.add_member(workspace_id, email, body.name)
    return {"workspaceId": membership.workspace_id, "userId": membership.user_id}
