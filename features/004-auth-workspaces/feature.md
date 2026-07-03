---
slug: auth-workspaces
title: Auth & workspaces
outcome: Users sign in with Google or Microsoft (dev-login for local/e2e); the first user becomes admin, creates workspaces and adds members; datasets, catalogs and conversations are isolated per workspace. App state lives in embedded SQLite.
status: ready
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

> PRE-ALLOCATED STUB (parallel-session prep, 2026-07-03). Number and branch are
> fixed; the owning session fleshes this out via /engineer.prime-context →
> /engineer.discover-acs → /engineer.atdd → /engineer.plan → implement.
> Ownership boundaries + kickoff prompt: docs/PARALLEL_PLAN.md.
