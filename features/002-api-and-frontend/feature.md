---
slug: api-and-frontend
title: FastAPI layer & aligned frontend (design-prototype integration)
outcome: The analyst backend is reachable over HTTP (/api/*) with wire shapes sourced from the feature-001 domain, and a working React frontend (from the Claude Desktop Design prototype) renders profiling, catalog, ingestion, and provisional Q&A — against the real store by default, with a Python fixture mode retained for demos and deterministic e2e tests.
status: in-progress
autonomy_level: high
assignee: local
owner: igormusic
area: platform
roadmap_ref: react-tailwind-shadcn-frontend-app-shell
tracker_ref: local://api-and-frontend
branch: api-and-frontend
validation_method: "GWT acceptance spec bound to Playwright e2e running against the fixtures API (deterministic, no LLM); backend API tests via FastAPI TestClient; frontend lint/typecheck/build blocking in CI."
size: L
created: 2026-07-02
---

# Feature 002 — FastAPI layer & aligned frontend

> Integration of the Claude Desktop Design clickable prototype (delivered as
> `dist-repo`, see `CONTRACT.md`). The prototype is the approved design; ACs are
> derived from its implemented behavior rather than a fresh discovery interview
> (compressed DAE pipeline — deviation approved by the human 2026-07-02).

## Outcome

1. **API layer** (`src/analyst/api/`): FastAPI serving `/api/*` — datasets,
   profiles, catalog, multipart ingest, ingestion status, refresh, delete,
   health — with pydantic schemas mirroring `analyst.domain.*` (camelCase wire).
2. **Repository seam**: `StoreRepository` (real `IngestionService` + DuckDB,
   **default**) vs `FixtureRepository` (in-memory mock built from real domain
   dataclasses, opt-in via `ANALYST_FIXTURES=1`) — retained for demos and e2e.
3. **Frontend** (`frontend/`): the aligned React/Zustand app (Ingestion +
   Workspace pages, Q&A panel with clarifications + trust trail) replacing the
   old drifted WIP frontend. HTTP-only client; no TS mocks.
4. **Q&A endpoints are PROVISIONAL** (feature 002-qa has no domain yet): canned
   responses built on the domain `Clarification` primitive; wire shape stable.

## Scope

**In:** everything in APPLY.md; flipping the fixture default to off; the missing
`refresh` endpoint; backend API tests; Playwright e2e bound to a GWT spec via
the DAE acceptance pipeline; blocking frontend CI; root Makefile + CONTRACT.md.

**Out:** real NL→SQL Q&A (future feature); auth/workspaces; Tailwind/shadcn
migration (the prototype ships hand-rolled CSS in the Swiss style — the PRD
originally named Tailwind/shadcn; deviation noted, revisit when the design
system is formalized); dashboards.

## Context & sources

- `CONTRACT.md` (repo root) — field-by-field domain↔wire alignment.
- `docs/PRD.md` §8, §9 — API/frontend architecture; AskQuestion primitive.
- Prototype package: Claude Desktop Design export, applied per its APPLY.md.
