# Acceptance criteria — Feature 004: Auth & workspaces

> Checkpoint 2 (discover-acs). PRD FR-14/15/16, CHARTER §2 (SQLite app state),
> docs/PARALLEL_PLAN.md 004 notes. Autonomy: high — no human gate; the runbook
> carries the one human item (real OAuth credentials).
>
> Key design constraint: **auth is opt-in by configuration.** When no login
> method is configured (no OAuth client env vars and `ANALYST_DEV_LOGIN`
> unset) the API and app behave exactly as before feature 004 — features
> 001/002 boards and unit tests stay green unchanged.

## API contract (HTTP)

- **AC-1 — Sign-in discovery.** `GET /api/auth/providers` reports which
  sign-in methods are available. With only dev sign-in enabled it offers
  dev sign-in and reports Google and Microsoft as not configured.
- **AC-2 — Session enforcement.** When a login method is configured, `/api/*`
  requires a session: a signed-out client listing datasets is rejected as
  unauthenticated (401); `/api/health` stays open.
- **AC-3 — First user becomes admin.** The first user ever to sign in becomes
  admin and receives a default workspace. A later user is not admin and
  belongs to no workspace until added.
- **AC-4 — Admin manages workspaces and members.** The admin can create a
  workspace and add a member by e-mail; the member sees that workspace after
  signing in. Non-admins cannot create workspaces or add members.
- **AC-5 — Workspace isolation.** Datasets are scoped to the active
  workspace: deleting a dataset in one workspace does not affect another.
- **AC-6 — Sign-out.** Signing out ends the session; the old session token
  can no longer reach workspace data.
- **AC-7 — Unconfigured OAuth is refused clearly.** Starting a Google or
  Microsoft sign-in while that provider is not configured is refused with a
  message saying it is not configured.
- **AC-8 — Backward compatibility.** With no sign-in method configured the
  API serves all requests without any session, exactly as before.

## Frontend flows (browser)

- **AC-9 — Dev sign-in flow.** An unauthenticated visitor sees the sign-in
  page; signing in with the dev sign-in (name only) lands in the workspace
  app with their name shown in the header.
- **AC-10 — Unconfigured OAuth is stated.** The sign-in page says Google
  sign-in and Microsoft sign-in are not configured (when they are not).
- **AC-11 — Workspace management and isolation in the UI.** The admin can
  create a workspace from the header and switch between workspaces; the
  semantic catalog shows each workspace's own datasets (a deletion in one
  workspace does not leak into another).
- **AC-12 — Sign-out flow.** Signing out returns the visitor to the sign-in
  page.
- **AC-13 — No-workspace notice.** A signed-in user who belongs to no
  workspace sees a notice that no workspace has been assigned yet.
