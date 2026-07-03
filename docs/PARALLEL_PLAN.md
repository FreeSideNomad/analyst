# Parallel implementation plan — remaining features

> Written 2026-07-03 (human-approved). Three cloud sessions (claude.ai/code)
> implement wave 1 in parallel; the local integrator session merges, resolves
> conflicts, and keeps the boards green. Every feature is a **vertical slice**
> (domain → engine/agentic → API → UI → e2e) per CHARTER §6: the GWT spec must
> cover the API contract (HTTP-bound) AND the UI flows (Playwright-bound).

## Waves

```
WAVE 1 (parallel, now)                  WAVE 2 (parallel, after wave 1)   WAVE 3
003 NL Q&A over a dataset ──────────┬── 009 Cross-dataset joins ←────┐
004 Auth & workspaces               │                                 │
005 Relational DB federation ───────┴── 006 PK/FK discovery ──────────┘
                                        007 Normalization detection
                                        008 Charts & data exports ─────── 010 Interactive dashboards (needs 003+008)
```

Feature numbers 003–005 are **pre-allocated** (stub folders exist) so parallel
sessions never race DAE numbering. Branch name == slug (in `feature.md`).

## Ownership boundaries (wave 1)

| Surface | 003 nl-qa | 004 auth-workspaces | 005 db-federation |
|---|---|---|---|
| domain | `domain/query*` (new) | — | `domain/connection*` (new) |
| engine | query execution helpers | — | `engine/federation*` (ATTACH, live profiling) |
| agentic | `agentic/planner*` (new), prompts | — | — |
| persistence | — | `persistence/` (new, SQLite app state) | — |
| api | `api/routes/qa.py`, `api/qa.py` | `api/routes/auth.py` (new), auth middleware in `app.py`¹ | `api/routes/databases.py` (new) |
| repository | Q&A fixture path | workspace scoping¹ | connection records¹ |
| frontend stores | `stores/query-store.ts` | `stores/auth-store.ts` (new) | `stores/catalog-store.ts` additions¹ |
| frontend pages | `pages/WorkspacePage.tsx` Q&A section¹ | `pages/LoginPage.tsx` (new), `Header.tsx`¹ | CatalogTree "Connect a database"¹ |
| acceptance | `acceptance/e2e_003.py` (new) | `acceptance/e2e_004.py` (new) | `acceptance/e2e_005.py` (new) |
| fixtures | deterministic Q&A answers | dev-login user/workspace seed | fixture attached SQLite DB |

¹ = shared file. Rule: **only touch a shared file for your marked concern, keep
the diff minimal, and note it in your PR description** — the integrator handles
merge order. Everything unmarked is owned exclusively.

Shared-by-everyone (expect trivial conflicts; integrator resolves): `app.py`
router includes, `pyproject.toml`/`uv.lock`, `frontend/package.json`/`bun.lock`.

## Per-feature notes

### 003 — NL Q&A (`features/003-nl-qa/`)
- Real mode: planner = semantic catalog + profiles → SQL via the Claude Agent
  SDK (through the **LLMGateway** — governance: only metadata/samples/small
  results cross; SQL executes locally in DuckDB). Confidence gating → AskQuestion;
  self-verification checks before answering; abstain when out-of-scope.
  Trust trail populated from the real plan (assumptions, lineage, SQL).
- Fixtures mode: keep a deterministic path (canned or recorded-real) so the
  existing + new UI e2e stays LLM-free. **The wire contract (CONTRACT.md Q&A
  shapes) must not change** — the frontend already speaks it.
- Record/replay: extend `tests/cassettes/` (see `tests/unit/test_agentic.py`
  pattern; `uv run pytest -m live` records). If live model access is unavailable
  in the cloud VM, build against the replay seam and ask the integrator session
  to record cassettes locally.
- Update `/api/health` `qa` field from "provisional" when real.

### 004 — Auth & workspaces (`features/004-auth-workspaces/`)
- SQLite app state (users, workspaces, memberships) in a new `persistence/`
  module — per CHARTER: SQLite for transactional state, DuckDB for analytics.
- OAuth (Google + Microsoft) behind config; **dev-login** (name-only) for local
  dev + e2e — enabled only when fixtures/dev mode. First user = admin.
- Workspace scoping: per-workspace `ANALYST_DATA_DIR` subdirs + repository
  scoping; `/api/*` guarded by session middleware (health + login exempt).
- Real OAuth client IDs/secrets are a **runbook item for the human** — build,
  test with dev-login, document the console steps.

### 005 — DB federation (`features/005-db-federation/`)
- DuckDB `ATTACH` for SQLite (deterministic tests + fixture), Postgres/MySQL via
  DuckDB extensions (live-marked tests; document docker recipe in runbook).
- Nothing copied: live profiling through the attachment (feature-001 profiler
  works on any relation). Declared PK/FK read into the catalog where available.
- API: connect/list/detach endpoints (`routes/databases.py`); connection
  secrets never returned. UI: the CatalogTree "Connect a database — soon"
  placeholder becomes a real flow.
- Golden data: Chinook SQLite from `docs/golden-corpus.md` (MIT, downloadable).

## Definition of done (every feature)
1. DAE artifacts: acs.md (API + UI-flow sections), spec.md (all ACs → scenarios),
   plan.md (architecture human-confirmed), handoffs.
2. Boards green: its own spec board + **all pre-existing boards** (001, 002, …).
3. Unit tests; mypy/ruff clean; frontend tsc/oxlint/build clean.
4. Fixture mode extended; UI carries stable accessible labels.
5. `.handlers` file points at the feature's e2e module (`acceptance/e2e_<NNN>…`),
   built on `acceptance/e2e_base.py`. The runner + CI auto-discover it.
6. PR to `main` with CI green; note any shared-file touches in the description.

## Cloud session setup (one-time, human)
1. claude.ai/code → connect the GitHub account/repo (`FreeSideNomad/analyst`).
2. Create a cloud environment for the repo. Suggested setup commands (mirrors CI):
   `uv sync && (cd frontend && bun install) && uv run playwright install --with-deps chromium`
3. Launch three sessions, one per kickoff prompt below.
4. Tell the integrator session the setup is done (it flips `manifest.remote`).

## Kickoff prompts (paste one per cloud session)

### Session A — 003 NL Q&A
```
Work ONLY on feature 003 in this repo. Read docs/PARALLEL_PLAN.md (ownership
boundaries — you own the Q&A surface; minimal diffs on shared files), CHARTER.md,
docs/PRD.md §8.3, CONTRACT.md, and features/003-nl-qa/feature.md. Create branch
nl-qa from main. Run the DAE pipeline: /engineer.prime-context →
/engineer.discover-acs → /engineer.atdd → /engineer.plan → implement (TDD,
acceptance-first). ACs must cover the API contract AND UI e2e flows (Playwright
via acceptance/e2e_base.py; see feature 002's spec/handlers as the template).
Keep the Q&A wire contract stable; keep fixtures mode deterministic; real mode
uses the Claude Agent SDK through the LLMGateway with record/replay cassettes.
All pre-existing boards (./run-acceptance-tests.sh) must stay green. Finish with
a PR to main.
```

### Session B — 004 Auth & workspaces
```
Work ONLY on feature 004 in this repo. Read docs/PARALLEL_PLAN.md (ownership
boundaries — you own auth/persistence/login; minimal diffs on shared files),
CHARTER.md, docs/PRD.md §8.4, and features/004-auth-workspaces/feature.md.
Create branch auth-workspaces from main. Run the DAE pipeline:
/engineer.prime-context → /engineer.discover-acs → /engineer.atdd →
/engineer.plan → implement (TDD, acceptance-first). ACs must cover the API
contract AND UI e2e flows (Playwright via acceptance/e2e_base.py). Build OAuth
behind config with a dev-login for local/e2e (first user = admin, workspace
isolation); real Google/Microsoft client credentials are a runbook item for the
human — do not block on them. All pre-existing boards must stay green. Finish
with a PR to main.
```

### Session C — 005 DB federation
```
Work ONLY on feature 005 in this repo. Read docs/PARALLEL_PLAN.md (ownership
boundaries — you own engine/federation + database routes/UI; minimal diffs on
shared files), CHARTER.md, docs/PRD.md §6/§9, docs/golden-corpus.md, and
features/005-db-federation/feature.md. Create branch db-federation from main.
Run the DAE pipeline: /engineer.prime-context → /engineer.discover-acs →
/engineer.atdd → /engineer.plan → implement (TDD, acceptance-first). ACs must
cover the API contract AND UI e2e flows (Playwright via acceptance/e2e_base.py);
deterministic tests use SQLite ATTACH + the Chinook golden DB, Postgres/MySQL
behind live markers with a runbook docker recipe. Nothing is copied — federated
query-through only. All pre-existing boards must stay green. Finish with a PR
to main.
```

## Integrator protocol (the local session)
- Merge PRs in readiness order; after each merge: re-run all boards, fix
  trivial conflicts (`uv.lock`, router includes, bun.lock), push, then tell the
  other sessions to rebase onto main.
- Keep roadmap/tracker current (mark in-progress at kickoff, shipped at merge).
- Record LLM cassettes locally if a cloud session can't.
- After wave 1 fully merges: pre-allocate 006–008 stubs and launch wave 2.
