---
slug: semantic-depth
checkpoint: 4
plan_status: proposed
created: 2026-07-04
---

# Plan — Feature 009: Semantic depth

## Architecture

### Domain (new value object)
- **`domain/relationships.py` — `Relationship`** (frozen): `child_table`,
  `child_column`, `parent_table`, `parent_column`, `origin`
  (`"declared" | "inferred"`), `join_type` (`"required" | "optional"`),
  `coverage: float` (RI match fraction, 1.0 for declared). Single-column only.
- **`CatalogEntry` gains `relationships: tuple[Relationship, ...]`** (the ones
  *this* table participates in) for display; the planner reads the workspace-wide
  union.

### Discovery engine (new, local, governance-safe)
- **`engine/relationships.py` — `discover(con, tables) -> list[Relationship]`**,
  run in the same DuckDB connection that already holds files (parquet views) and
  connected DB tables (scanner views) — so **cross-source is uniform** (a file
  and a DB table are both just relations in `con`).
  - **Declared** — from the federation bridges' existing `declared_keys()`
    (`TableKeys`), lifted into `Relationship(origin="declared", coverage=1.0)`.
  - **Implied (single-column)** — candidate pairs by a name heuristic
    (`X_id`/`Xid`/`X` → a table `X`/`Xs` whose key/`id`/PK column has a
    compatible type), then **validated by referential integrity in DuckDB**:
    `SELECT count(*) FROM child WHERE col IS NOT NULL AND col NOT IN (SELECT key FROM parent)` — zero ⇒ accept. `join_type = optional` iff the child
    column has nulls, else `required`; `coverage` = matched / non-null.
  - Name-only matches that fail RI are dropped (AC-7); on multiple passing
    parents, keep the best coverage (ties → a needs-review clarification).
- No bulk data crosses to the LLM — pure set queries (AC-15).

### Richer cataloguing (`agentic/cataloguer.py` + payload)
- Feed the **distribution** (already computed in 006) and the discovered
  relationships into the `CatalogPayload`; strengthen the prompt so each column
  description is grounded in name + samples + distribution (AC-8) and the table
  description **aggregates** its columns and relationships (AC-9).
- **DB tables run the real `Cataloguer`**, not `catalog_for_table` — the stub
  becomes the *pending placeholder* only (see async below). AC-10.

### Async DB cataloguing (`api/repository.py` + a background worker)
- On connect: create records immediately with the deterministic stub +
  `catalog_status = "pending"`; **return promptly** (AC-11). A bounded
  background worker (a `ThreadPoolExecutor` owned by the repo, capped
  concurrency) catalogues each table via the `Cataloguer`, writing the real
  entry + `catalog_status = "complete"` (or `"failed"`, AC-16) back to the store.
- **Status surface:** `DatasetSchema` gains `catalogStatus`; the frontend already
  refetches `/api/datasets` — a short poll while any table is `pending` drives
  the refresh. (Mirrors the existing ingestion-status poll; no new socket.)

### API / wire
- `CatalogEntrySchema` gains `relationships`; `DatasetSchema` gains
  `catalogStatus`. Relationships carry origin + joinType + coverage.

### Frontend (workbench)
- **Table detail** — a "Relationships" block: related-to links, each badged
  declared/inferred + required/optional (AC-12). Pending DB tables show a
  "cataloguing…" state and refresh when done (AC-11).
- **Column drilldown** — shows the column's FK relationship, if any (AC-13).

### Planner (`agentic/planner.py`)
- `_flatten`/the prompt gain the workspace relationships; generated SQL joins on
  them with the recorded join type (required→inner, optional→outer). Observable
  today for **file** Q&A (AC-14); DB Q&A lands with 007/008.

### Persistence
- Relationships + `catalog_status` persist in the existing catalog sidecar
  (`_save/_load_catalog_sidecar`), so they survive restart (AC-16).

## Charter Check
| Rule | Status |
|---|---|
| Layered architecture (domain → engine → agentic → api → frontend) | ✅ discovery in `engine`, `Relationship` in `domain`, enrichment in `agentic` |
| Governance invariant (only schema/profiles/samples to LLM) | ✅ RI + distributions computed locally; AC-15 asserts it |
| ATDD (spec → red board → implement) | ✅ 18-scenario red board stands |
| Autonomy / verification independence | ✅ deterministic tests (cassettes); live opt-in |
| **Deviation — background worker** | ⚠️ async cataloguing adds a bounded in-process thread pool (new concurrency). **Amendment:** capped concurrency + reuses the store's existing `RLock`; failures are contained per-table (AC-16); no cross-process/queue infra — stays within the single-image box. |

## Phasing (slices, each red→green on its scenarios)
- **A — discovery core:** `Relationship` + `engine/relationships.py` (declared +
  implied single-col + RI + join_type, within-source) + unit tests. AC-1,2,3,4,5,7.
- **B — cross-source:** file↔DB discovery in the shared DuckDB connection. AC-6.
- **C — richer cataloguing:** data-grounded column + aggregated table
  descriptions; real `Cataloguer` on DB tables. AC-8,9,10.
- **D — async cataloguing:** background worker + `catalogStatus` + progress UI +
  refresh. AC-11.
- **E — surface on focus:** relationships in table detail + column drilldown;
  wire. AC-12,13.
- **F — feed the planner:** relationships in the payload; file joins use them. AC-14.
- **G — cross-cutting + acceptance:** persistence, failure containment,
  governance; `e2e_009` bindings; board green. AC-15,16.

## Performance budget
- Discovery: name-heuristic prunes candidates; ≤ one DuckDB set-query per
  surviving candidate. Cross-source RI is a single scanner-backed join.
- Async cataloguing: N model calls per DB, **backgrounded** + concurrency-capped
  + opt-out via env for very large schemas; connect latency unaffected.

## Test strategy
Per `validation_method`: backend unit tests for discovery / RI / join-type /
coverage over **synthetic + Chinook/Pagila** data; GWT acceptance — Playwright
for focus + async-progress, in-process/HTTP for discovery + planner; the
cataloguer LLM via **cassettes** (deterministic), `live` opt-in. mypy/ruff +
frontend tsc/oxlint/build. **All boards 001–006 stay green.**
