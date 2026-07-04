"""Persistence-layer tests (feature 004) — AppState (SQLite) + token signing."""

from __future__ import annotations

from analyst.persistence import AppState, sign, unsign
from analyst.persistence.appstate import DEFAULT_WORKSPACE_NAME


# --------------------------------------------------------------------------- #
# Signing — HMAC tokens
# --------------------------------------------------------------------------- #
def test_sign_and_unsign_roundtrip():
    token = sign("session-id", "secret")
    assert unsign(token, "secret") == "session-id"


def test_unsign_rejects_tampering_and_wrong_secret():
    token = sign("session-id", "secret")
    assert unsign(token, "other-secret") is None
    assert unsign(token.replace("session", "hijack"), "secret") is None
    assert unsign("garbage", "secret") is None
    assert unsign("", "secret") is None


# --------------------------------------------------------------------------- #
# AppState — users & first-user-is-admin
# --------------------------------------------------------------------------- #
def test_first_user_becomes_admin_with_default_workspace():
    state = AppState()
    ana = state.sign_in("ana@dev.local", "Ana", "dev")
    assert ana.is_admin is True
    workspaces = state.workspaces_for(ana.id)
    assert [w.name for w in workspaces] == [DEFAULT_WORKSPACE_NAME]


def test_second_user_is_not_admin_and_has_no_workspace():
    state = AppState()
    state.sign_in("ana@dev.local", "Ana", "dev")
    ben = state.sign_in("ben@dev.local", "Ben", "dev")
    assert ben.is_admin is False
    assert state.workspaces_for(ben.id) == []


def test_sign_in_is_idempotent_by_email():
    state = AppState()
    first = state.sign_in("ana@dev.local", "Ana", "dev")
    again = state.sign_in("Ana@Dev.Local", "Ana Maria", "google")
    assert again.id == first.id
    assert again.name == "Ana Maria" and again.provider == "google"
    assert again.is_admin is True  # admin bit survives re-sign-in


# --------------------------------------------------------------------------- #
# Workspaces & memberships
# --------------------------------------------------------------------------- #
def test_admin_creates_workspace_and_adds_member_by_email():
    state = AppState()
    ana = state.sign_in("ana@dev.local", "Ana", "dev")
    finance = state.create_workspace("Finance", ana.id)
    assert state.is_member(ana.id, finance.id)
    # member added BEFORE ever signing in -> stub, claimed on sign-in
    state.add_member(finance.id, "ben@dev.local")
    stub = state.user_by_email("ben@dev.local")
    assert stub is not None and stub.has_signed_in is False
    ben = state.sign_in("ben@dev.local", "Ben", "dev")
    assert ben.id == stub.id and ben.has_signed_in
    assert [w.name for w in state.workspaces_for(ben.id)] == ["Finance"]


def test_members_listing_and_duplicate_add_is_harmless():
    state = AppState()
    ana = state.sign_in("ana@dev.local", "Ana", "dev")
    finance = state.create_workspace("Finance", ana.id)
    state.add_member(finance.id, "ben@dev.local", "Ben")
    state.add_member(finance.id, "ben@dev.local", "Ben")
    assert [u.email for u in state.members_of(finance.id)] == [
        "ana@dev.local",
        "ben@dev.local",
    ]


# --------------------------------------------------------------------------- #
# Sessions
# --------------------------------------------------------------------------- #
def test_session_lifecycle_defaults_to_first_workspace():
    state = AppState()
    ana = state.sign_in("ana@dev.local", "Ana", "dev")
    default_ws = state.workspaces_for(ana.id)[0]
    session = state.create_session(ana.id)
    assert session.workspace_id == default_ws.id
    fetched = state.get_session(session.id)
    assert fetched is not None and fetched.user_id == ana.id
    state.delete_session(session.id)
    assert state.get_session(session.id) is None


def test_session_without_workspace_and_switching():
    state = AppState()
    ana = state.sign_in("ana@dev.local", "Ana", "dev")
    ben = state.sign_in("ben@dev.local", "Ben", "dev")
    ben_session = state.create_session(ben.id)
    assert ben_session.workspace_id is None
    finance = state.create_workspace("Finance", ana.id)
    state.add_member(finance.id, ben.email)
    state.set_active_workspace(ben_session.id, finance.id)
    refetched = state.get_session(ben_session.id)
    assert refetched is not None and refetched.workspace_id == finance.id


def test_expired_sessions_are_rejected(monkeypatch):
    import analyst.persistence.appstate as appstate_mod

    state = AppState()
    ana = state.sign_in("ana@dev.local", "Ana", "dev")
    monkeypatch.setattr(appstate_mod, "SESSION_TTL_SECONDS", -1)
    session = state.create_session(ana.id)
    assert state.get_session(session.id) is None


def test_file_backed_state_persists(tmp_path):
    db = tmp_path / "nested" / "app.sqlite3"
    AppState(db).sign_in("ana@dev.local", "Ana", "dev")
    reopened = AppState(db)
    ana = reopened.user_by_email("ana@dev.local")
    assert ana is not None and ana.is_admin is True
