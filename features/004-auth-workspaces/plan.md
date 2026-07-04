# Plan — Feature 004: Auth & workspaces

> Checkpoint 4. Architecture per CHARTER §2 (SQLite for app state, embedded,
> no separate DB container) and docs/PARALLEL_PLAN.md ownership boundaries.

## Shape

```
frontend  LoginPage ── auth-store ──► /api/auth/*        App.tsx auth gate
          Header ► WorkspaceControls (switcher, create, sign out)
api       routes/auth.py   session middleware + auth/workspace routes
          deps.py          get_repository → per-workspace repo (fixtures or store)
          routes/system.py /api/_reset also resets auth state (fixtures only)
persistence appstate.py    SQLite: users, workspaces, memberships, sessions
            signing.py     HMAC-signed opaque tokens (cookie + OAuth state)
domain    user.py, workspace.py   pure dataclasses
```

## Decisions

1. **Auth is opt-in by configuration.** `auth_enabled()` = dev sign-in
   (`ANALYST_DEV_LOGIN=1`) or any OAuth provider configured via env. When
   disabled, the HTTP middleware passes everything through and
   `get_repository` returns the single default repository — byte-for-byte
   the pre-004 behavior. This is the backward-compat guarantee for the
   001/002 boards.
2. **Sessions**: server-side rows in SQLite keyed by a random id; the cookie
   carries `id.hmac(id)` (HTTP-only, SameSite=Lax). Stdlib `hmac`/`secrets`
   only — no new heavyweight deps. Secret from `ANALYST_SESSION_SECRET` or a
   per-process random (dev). Logout deletes the row (real revocation).
3. **App state**: `persistence.AppState` wraps a single SQLite connection
   (thread-safe via a lock). Store mode: `<data_dir>/app.sqlite3`; fixtures
   mode: in-memory. First user ever → `is_admin=1` + a default workspace
   named "Default". Admin adds members by e-mail — a stub user row is
   created if the member has not signed in yet and is claimed on first
   sign-in (OAuth or dev) by e-mail match.
4. **Workspace scoping**: the repo holder gains a `workspaces` dict —
   per-workspace `FixtureRepository()` (fresh seed each) or
   `StoreRepository(<data_dir>/workspaces/<ws-id>)`. `get_repository` picks
   by the session's active workspace; no dataset/qa route changes.
5. **OAuth** (Google + Microsoft, authorization-code): authorize-redirect and
   callback handlers built and unit-tested against a seam
   (`_exchange_code`); real client ids/secrets are env-configured and a
   RUNBOOK item. e2e uses dev sign-in only.
6. **e2e stack**: `acceptance/e2e_004.py` defines its own copy of the session
   stack fixture (adds `ANALYST_DEV_LOGIN=1`) rather than touching the
   shared `e2e_base.py`.

## Steps (test-first)

1. acs/spec/runbook artifacts (done above).
2. `persistence/` + domain dataclasses + `tests/unit/test_persistence.py`.
3. `routes/auth.py` (middleware, providers/dev-login/me/logout/switch,
   workspaces admin routes, OAuth redirect/callback) + `deps.py` scoping +
   `system.py` reset hook + `tests/unit/test_auth_api.py`.
4. Frontend: `stores/auth-store.ts`, `pages/LoginPage.tsx`,
   `components/WorkspaceControls.tsx`, App gate, Header additions.
5. `acceptance/e2e_004.py` + `.handlers`; run the 004 board, then all boards.
6. Gates: pytest, mypy, ruff, bun lint/build; commit in logical slices.
