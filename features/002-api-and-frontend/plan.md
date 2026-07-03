---
slug: api-and-frontend
checkpoint: 4
plan_status: approved
created: 2026-07-02
---

# Plan — Feature 002: FastAPI layer & aligned frontend

Human-approved 2026-07-02 (plan presented in-session before execution).
Compressed DAE pipeline: the Claude Desktop Design prototype is the approved
design, so ACs derive from it; the GWT spec binds to Playwright as the
acceptance layer.

## Architecture

- **`src/analyst/api/`** — new API layer (FastAPI). Depends inward on
  domain/service/engine only; no business logic. Pydantic schemas mirror
  `analyst.domain.*` via `from_domain` (camelCase wire; see `CONTRACT.md`).
- **Repository seam** — `DatasetRepository` protocol; `StoreRepository`
  (real `IngestionService`+`DatasetStore`, **default**) vs `FixtureRepository`
  (in-memory mock built from real domain dataclasses; `ANALYST_FIXTURES=1`).
  Fixtures retained for demos + deterministic e2e — **not** the default
  (flipped from the prototype package per human decision).
- **`frontend/`** — React + Zustand + hand-rolled Swiss CSS (prototype
  fidelity; Tailwind/shadcn deviation noted in feature.md). HTTP-only client;
  Vite dev proxy `/api → :8000`.
- **Q&A endpoints provisional** — canned (`api/qa.py`) regardless of mode until
  the Q&A feature lands; wire shape mirrors the domain `Clarification`.

## Key decisions

- **D1 — fixtures opt-in, not default** (`ANALYST_FIXTURES` unset/0 → real store).
- **D2 — e2e = GWT spec + Playwright binding** through the same DAE acceptance
  pipeline as feature 001 (spec.md → IR → generated pytest), with step handlers
  driving Chromium via Playwright's sync Python API against uvicorn(fixtures) +
  the built frontend. One acceptance toolchain; deterministic (no LLM).
- **D3 — frontend CI becomes blocking** (lint + typecheck + build) now that the
  frontend is real, aligned code; new e2e CI job.
- **D4 — missing `refresh` endpoint** (in CONTRACT, absent from app.py) is wired
  to the feature-001 `IngestionService.refresh`.

## Phasing

A. Copy per APPLY.md (keep old frontend's .gitignore/.oxlintrc/favicon); deps.
B. Flip fixture default; add refresh endpoint; backend gate green.
C. Backend API tests (TestClient; fixtures + real-store paths).
D. Frontend hygiene: bun lockfile, lint script, tsc in build; all green.
E. GWT spec + Playwright handlers via the acceptance pipeline; e2e green.
F. CI (blocking frontend, e2e job), docs, PR.

## Test strategy

- **Acceptance:** `features/002-api-and-frontend/spec.md` (GWT) → Playwright
  e2e on fixtures (AC-6..10) + TestClient bindings (AC-1..5 covered in unit).
- **Unit:** `tests/unit/test_api.py` — endpoints, both repositories, 404/204.
- **Static:** mypy on `src/analyst/api`; oxlint + `tsc --noEmit` on frontend.
- Per `validation_method`: everything deterministic; no live LLM in CI.
