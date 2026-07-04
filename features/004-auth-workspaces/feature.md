---
slug: auth-workspaces
title: Auth & workspaces
outcome: Users sign in with Google or Microsoft (dev-login for local/e2e); the first user becomes admin, creates workspaces and adds members; datasets, catalogs and conversations are isolated per workspace. App state lives in embedded SQLite.
status: done
autonomy_level: high
assignee: cloud
owner: igormusic
area: platform
roadmap_ref: auth-workspaces
tracker_ref: local://auth-workspaces
branch: auth-workspaces
validation_method: "Full-stack DoD (CHARTER §6): GWT spec with API-contract + UI-e2e scenarios (Playwright on fixtures), unit tests, mypy/ruff/tsc/oxlint; LLM paths use recorded-real cassettes + opt-in live evals."
size: L
created: 2026-07-03
---

# Feature 004 — Auth & workspaces

Implemented 2026-07-03 on branch `auth-workspaces` (parallel wave 1, session B).

- **Sign-in**: Google + Microsoft OAuth (authorization-code, env-configured —
  real credentials are a human item, see `runbook.md`) and a name-only **dev
  sign-in** enabled by `ANALYST_DEV_LOGIN=1` (local dev + e2e).
- **Opt-in enforcement**: with no login method configured the API behaves
  exactly as before this feature (001/002 boards unchanged). Once configured,
  `/api/*` needs a session except `/api/health`, `/api/auth/*` and — fixtures
  mode only — `/api/_reset`.
- **Roles**: first user ever to sign in becomes admin and gets the "Default"
  workspace; the admin creates workspaces and adds members by e-mail.
- **Isolation**: datasets/catalogs are scoped to the session's active
  workspace (per-workspace repository under `<data_dir>/workspaces/<id>`;
  fresh-seeded fixture repository per workspace in fixtures mode).
- **App state**: users/workspaces/memberships/sessions in embedded SQLite
  (`src/analyst/persistence/`), per CHARTER §2.

Artifacts: `acs.md` (13 ACs), `spec.md` (13 scenarios: 8 HTTP + 5 Playwright,
board bound via `.handlers` → `acceptance.e2e_004`), `plan.md`, `runbook.md`
(human OAuth console steps), `handoffs/`.
