---
slug: file-ingestion-and-profiling
checkpoint: 4
plan_status: draft
created: 2026-07-01
---

# Plan — Feature 001: File ingestion & agentic data profiling

## Architecture

Layered per CHARTER §2; dependencies point inward (domain ← engine ← agentic/api).

### Components

1. **Domain / core** (pure Python, no I/O, no framework imports)
   - Entities/value objects: `Dataset`, `DatasetVersion`, `ColumnProfile`, `DatasetProfile`, `CatalogEntry`, `ColumnDescription`, `ColumnRole`, `IngestionResult`, `Clarification` (AskQuestion payload: question + options), `SchemaValidationResult`.
   - `ColumnType` enum: text, integer, decimal, boolean, date, datetime (+ an internal `mixed→text` widening rule).

2. **Data engine** (DuckDB + Parquet)
   - `FileReader` adapters: CSV/TSV/JSON via DuckDB native readers (`read_csv_auto`, `read_json_auto`) for scale; Excel via a library (per-sheet) with a size guard.
   - `EncodingDetector` (charset detection) and `HeaderDetector` (is row 1 a header?).
   - `Profiler` — **deterministic** stats computed set-based *in DuckDB*: inferred type, null rate, cardinality, distinct/sample values, numeric min/max/quantiles, distribution summary, mixed-type detection (→ widen to text + record dominant type & off-type examples). Duplicate-column disambiguation.
   - `Materializer` → Parquet; registers the dataset for querying.
   - `DatasetStore` — dataset lifecycle: create, version, refresh, delete.

3. **Agentic layer** (Claude Agent SDK) — **behind a single `LLMGateway`**
   - `LLMGateway` — the **only** path to the model. Enforces the sample cap; writes the **egress log**; guarantees no bulk rows are sent. This is the seam that makes AC-16 a unit-testable invariant.
   - `Cataloguer` — schema + profiles + capped samples → table/column descriptions + inferred roles.
   - `Clarifier` — emits a structured `Clarification` (AskQuestion) when cataloguing confidence is very low (AC-22).

4. **API** (FastAPI) — thin; wraps the facade below.

5. **`IngestionService` facade** (application layer) — orchestrates engine + agentic layer; **the seam the acceptance suite drives in-process** (fast, deterministic). FastAPI delegates to it.

6. **Persistence**
   - **SQLite** — transactional app state: datasets, versions, catalog entries, egress log, the (single default) workspace.
   - **DuckDB / Parquet** — analytical data.
   - Both file-backed inside the image/volume (single self-contained image).

### Data flow (ingest)
`file → FileReader (+encoding/header detect) → DuckDB register → Profiler (deterministic) → Materializer (Parquet) → LLMGateway→Cataloguer (descriptions/roles) → CatalogEntry persisted (SQLite)`. All-or-nothing: nothing persists unless the whole chain succeeds (AC-17).

### Key decisions (confirmed with human)
- **D1 — Deterministic profiling; LLM only descriptions/roles.** All type/null/cardinality/distribution work is deterministic in DuckDB (reproducible, no live LLM). The model is confined to the cataloguing step. Sidesteps the unresolved LLM-vs-statistics debate (FK discovery is not in 001). *Alt considered: LLM-assisted type inference — rejected for reproducibility/testability.*
- **D2 — In-process `IngestionService` seam for acceptance tests.** Fast/deterministic for 29 scenarios; FastAPI tested separately. *Alt: HTTP end-to-end — rejected as slow/flaky for the full suite.*
- **D3 — Fake LLM by default + separate live golden-eval.** Scenarios use a fake/recorded model; AC-16 asserted against the gateway; a live-gated golden-corpus eval (AC-24) runs the real model off the main suite. *Alt: always-mock — rejected because AC-24 would never measure real accuracy.*
- **D4 — Single `LLMGateway` chokepoint** for governance. Makes "no bulk data leaves the box" enforceable and testable in one place.
- **D5 — SQLite app state + DuckDB analytical** (per CHARTER). *Alt: DuckDB-only — rejected; OLAP store is weak for transactional app state.*

## Charter Check

| Charter rule | Status | Notes |
|---|---|---|
| uv for all Python (never bare pip/python3) | ✅ | uv for deps/run/venv |
| Latest Python, ruff, pytest, full type hints | ✅ | Python 3.14; ruff; pytest |
| Layered arch; domain core imports nothing outward | ✅ | Enforced by module structure; arch-check later |
| All Parquet/DuckDB access via data-engine layer | ✅ | No raw DuckDB in api/agentic code |
| Semantic catalog is the spine | ✅ | CatalogEntry produced every ingest |
| SQLite app state + DuckDB analytical | ✅ | D5 |
| Governance boundary (no bulk data leaves; auditable) | ✅ | D4 `LLMGateway` + egress log; AC-16 test |
| Inferences are test-validated, never silently applied | ✅ | Refresh validates before replace (AC-18); mixed-type recorded not asserted |
| Autonomy = high → performance budgets required | ✅ | See Performance budgets |
| Verification independence (verifier ≠ implementer) | ✅ | Enforced at CP6/7 via handoff agent_id |
| Mutation policy = opt_in per feature | ✅ | Opt-in; targeted at core profiling logic |

**No ⚠️ deviations → no amendment ADRs required.**

## Phasing (stages/slices — tasks emerge per spec/TDD cycle)

- **Slice A — Walking skeleton:** CSV → deterministic profile → Parquet/DuckDB → minimal CatalogEntry (no LLM), through `IngestionService`. Green: "A clean CSV becomes a profiled, queryable dataset". Establishes the seam + acceptance pipeline.
- **Slice B — Profiling depth:** rich types, null/cardinality/quantiles/distribution, mixed→text widening, header + encoding detection, duplicate-column disambiguation, empty/header-only handling. (Most edge + some error scenarios.)
- **Slice C — Formats:** Excel per-sheet, TSV, JSON (records + nested), unsupported-format rejection, malformed-file handling.
- **Slice D — Agentic cataloguing + governance:** `LLMGateway` (cap + egress log, AC-16), `Cataloguer` (descriptions/roles), `Clarifier`/AskQuestion (AC-22); fake LLM wired into the suite.
- **Slice E — Lifecycle:** refresh-with-validation + ask-to-loosen (AC-18), versioning (AC-19), delete (AC-20).
- **Slice F — Scale, observability, live eval, HTTP:** perf envelope + oversize rejection (AC-21), status observability (AC-23), live golden-corpus eval (AC-24), thin FastAPI layer.

## Performance budgets (high autonomy)

- Profiling is **set-based in DuckDB**, never row-by-row in Python.
- Ingest+profile a ~100 MB / ~1M-row CSV: target **< 30 s**; ~1 GB / few-million rows: **< ~3 min** (AC-21 envelope). Beyond envelope → immediate clear rejection (no hang).
- LLM cataloguing: **one bounded call per dataset** (schema + profiles + capped samples), never per-row. Sample cap small (e.g. ≤ N values/column) and enforced at the gateway.
- Typical aggregate query on materialized Parquet: **sub-second**.

## Collaboration schedule

- Human approved: charter, PRD, ACs, spec, this architecture.
- Human approves this `plan.md`, then implementation proceeds via `atdd:atdd-team` against the specs.
- Human review points remain at CP6 (refine) and CP7 (verify); verifier ≠ implementer.

## Execution modes

- **Local** subagents (feature `assignee: local`). Remote/cloud dispatch is **not ready** (no git origin; `manifest.remote.ready: false`) — stays local until an origin is added.

## Test strategy

- **Acceptance (WHAT):** the 29 scenarios, driven in-process through `IngestionService` with a **fake LLM**; golden-corpus fixtures (vendor the permissive small ones — Titanic, Northwind CSV, Superstore; fetch-at-test for share-alike/NC per `docs/golden-corpus.md`). AC-16 governance asserted against the gateway.
- **Unit (HOW):** per component — readers, encoding/header detection, each profiling statistic, type inference incl. mixed-widening, duplicate disambiguation, versioning, `LLMGateway` cap + egress-log enforcement, refresh schema-validation.
- **Mutation (opt-in):** targeted at the core `Profiler`/type-inference logic (highest-risk correctness).
- **Live golden-eval (AC-24):** separate, live-gated run of the real model on a few golden datasets; not on the main suite.
- **Manual smoke (`validation_method`):** via API/CLI, ingest representative clean + messy CSV/XLSX; assert profiling stats, Parquet/DuckDB registration, catalog entry, and that the egress log contains only schema/profiles/samples. (No staging environment exists yet.)

See `runbook.md` for operator setup (API key, deps, dataset download).
