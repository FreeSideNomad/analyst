---
slug: nl-qa
checkpoint: 4
plan_status: approved (autonomy high — no human gate; per kickoff)
created: 2026-07-03
---

# Plan — Feature 003: Natural-language Q&A over a dataset

Vertical slice: domain → agentic → engine helper → API → (frontend already
speaks the contract) → e2e. The wire contract (CONTRACT.md Q&A shapes) does
not change.

## Architecture

- **`domain/query.py`** (new, pure) — the Q&A domain model the API adapts:
  `PlanAction` (answer|clarify|abstain), `QueryPlan` (action, confidence, sql,
  title, assumptions, lineage, clarification, reason), `QueryColumn`/
  `QueryTable` (the metadata the planner sees — name, type, null rate,
  distinct count, sorted capped samples, catalog description/role), and
  `ResultTable` (small local result set). `query_table_from_summary()` builds
  a deterministic QueryTable from a `DatasetSummary` (samples sorted so
  record/replay keys are stable).
- **`domain/query_validation.py`** (new, pure) — closed-world SQL validation
  (FR-13): single statement, SELECT/WITH only, forbidden-keyword blocklist
  (INSERT/UPDATE/DELETE/DROP/CREATE/ATTACH/COPY/PRAGMA/…), every FROM/JOIN
  target must be a known dataset or CTE, every bare/qualified identifier must
  resolve to a known column, alias, table or CTE. Returns a list of problems;
  empty = valid. **SQL that fails validation is never executed.**
- **`agentic/planner.py`** (new) — `QueryPlanner`: one prompt-driven call per
  question **through the existing `LLMGateway`** (governance: the workspace
  metadata is flattened into a `CatalogPayload` whose columns are named
  `table.column`, so the gateway's sample cap + egress log apply unchanged;
  catalog descriptions are metadata rendered alongside). Structured JSON out
  (action/confidence/sql/assumptions/lineage/clarification/reason), parsed
  with pydantic; unparseable → abstain plan. Confidence gate: an "answer"
  below 0.5 confidence is demoted to an abstention with disclosure.
  `replan()` re-plans with the user's clarification choice appended.
- **`engine/query.py`** (new) — `run_select(store, sql, max_rows)`: executes
  validated SELECT SQL on the store's DuckDB connection, capped fetch, returns
  a domain `ResultTable`. Bulk data never leaves the box; only the small
  result set comes back. No existing engine file is modified.
- **`api/qa.py`** (rewrite, same wire shapes) — a `QAService` seam:
  - `CannedQAService` — the feature-002 deterministic path, kept verbatim for
    fixtures mode (UI e2e stays LLM-free).
  - `PlannerQAService` — real mode: repo records → sorted QueryTables → plan →
    validate → execute locally → shape `AnswerResult` (stat for 1×1 results,
    bar for small label/value results, plain otherwise; summary composed
    deterministically in Python from the executed result). Pending
    clarifications held per query id; respond re-plans with the choice.
  - `build_qa_service(repo)` — fixtures repo → canned; store repo → planner
    with `ClaudeAgentBackend` (or `ReplayBackend` when `ANALYST_QA_CASSETTE`
    is set — the deterministic e2e/demo seam).
- **`api/routes/qa.py`** — thin: lazily builds/holds the service on
  `app.state.qa_holder`, delegates. `app.py` untouched.
- **`api/routes/system.py`** (shared, minimal diff) — health `qa` field:
  `"canned"` in fixtures mode, `"real"` otherwise.
- **Frontend** — the contract is unchanged; `stores/query-store.ts` (owned)
  gains failure resilience only (an API error surfaces as an abstained local
  message instead of a stuck spinner). `WorkspacePage.tsx` untouched.

## Key decisions

- **D1 — validation failure abstains (no repair loop).** The brief allows
  repair *or* abstain; v1 abstains with disclosure — deterministic, never
  executes unvalidated SQL. A repair round-trip is a later refinement.
- **D2 — one model call per question; the answer summary is composed in
  Python from the locally executed result.** No second "phrase the answer"
  call: fewer cassettes, deterministic summaries, and no result rows need to
  cross to the model at all (stricter than the governance boundary requires).
- **D3 — respond() always returns an AnswerResult** (the wire contract). If a
  re-plan clarifies again, the service degrades to an abstained answer that
  says the question is still ambiguous.
- **D4 — record/replay via the gateway seam.** Live recorders (`-m live`)
  write real Opus responses to `tests/cassettes/planner.json`, keyed by the
  deterministic prompt hash (sorted tables/samples). Default runs replay. The
  e2e board boots a second uvicorn in real mode with a replay cassette and a
  real DuckDB store, so AC-1..AC-5 exercise the genuine planner→validate→
  DuckDB path over HTTP with zero live calls. The AC-5 (invalid SQL) cassette
  entry is synthesized in the e2e fixture through the same code path — it is
  test-authored by construction, not passed off as a model response.
- **D5 — fixtures Q&A stays byte-identical to feature 002** so the 002 board
  and existing UI e2e remain green.

## Test plan

- Unit: `test_query_validation.py` (pure validator), `test_planner.py`
  (replayed real plans + gating + parse failure + egress governance),
  `test_qa_service.py` (service orchestration with scripted backends on a real
  DuckDB store; invalid SQL never executes; respond flow; health/mode wiring).
- Acceptance: `acceptance/e2e_003.py` (this feature's board) — HTTP scenarios
  against the fixtures stack and the real-mode replay stack; UI scenarios via
  Playwright against the fixtures stack.
- Live (opt-in): `uv run pytest -m live tests/unit/test_planner.py` re-records
  the planner cassettes.
