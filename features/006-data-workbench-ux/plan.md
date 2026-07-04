---
slug: data-workbench-ux
checkpoint: 4
plan_status: proposed
created: 2026-07-04
---

# Plan — Feature 006: two-surface workbench UX

## Architecture

### Backend (small)
- **Dataset naming → `source.entity.ext`** (`service/ingestion.py`): a
  `_dataset_name(stem, entity, ext)` helper sanitizes each *segment* and joins
  with dots (dots preserved). Excel sheet → `<file>.<sheet>.xlsx`; single file →
  `<file>.<ext>`; DB table → `<connection>.<table>` (already fits). Verified the
  store handles dotted view names (quoted identifiers) and the versioned-parquet
  glob (`<name>.v*.parquet`) is dot-safe. Breaking change to dataset IDs —
  acceptable pre-release (a fresh data dir; old-named local data would just show
  under its old name).
- **Wire additions** (`api/schemas.py` `DatasetSchema`): expose `group` (first
  name segment) and `sourceKind` (`"file"` | `"database"`, from the existing
  `DatasetRecord.federated`) so the frontend can split Files/Databases and group
  without re-parsing. `queryable` (= not federated) for the AC-7 marking.

### Frontend (the bulk)
- **`IngestionPage` becomes the workbench:**
  - Left rail: a `SourceTree` with two sections (**Files** / **Databases**),
    grouped by `group`, expandable source → table → column. This is the
    `CatalogTree` from `WorkspacePage` moved and enhanced with grouping + the two
    sections + profile affordances.
  - Detail: a `TableDetail` merging the current `ProfileCard` stats with the
    `ColumnDetail` semantic view (table description, per-column description +
    role, needs-review); a `ColumnDrilldown` (stats + description) on select.
  - Add data: the existing `DatabasePanel` (feature 005) moves here beside the
    upload zone (connect / list / disconnect).
- **`WorkspacePage` → Query:** strip to `QueryChat` only; rename the header
  segment to "Query"; remove `CatalogTree` + `ColumnDetail` from it.
- **Stores:** reuse `catalog-store` (tree/selection state) + its connections
  state; no new store.

### Acceptance
- `acceptance/e2e_006.py` on `e2e_base` (Playwright). **Fixtures extended**
  (`api/fixtures.py`): add a multi-sheet-Excel-style trio (`company.employees.xlsx`,
  `company.departments.xlsx`) and a **fixture connected database** (`sales_db.*`
  records with `federated=True`) so grouping + the not-queryable marking are
  exercised without a real DB. Backend unit tests for `_dataset_name`.

## Charter check
- Layered architecture preserved (naming in `service`, wire in `api`, no domain
  change). ✅
- ATDD: spec → red board → implement. ✅
- No governance change (federated tables already excluded from Q&A). ✅
- Deviation: none.

## Phasing (slices, each red→green on its scenarios)
- **A — naming:** `_dataset_name` + wire `group`/`sourceKind`/`queryable` +
  unit tests (AC-3).
- **B — workbench browse:** SourceTree (Files/Databases, grouped) + TableDetail
  (profile + catalog) + ColumnDrilldown (AC-2,4,5,6).
- **C — connections in the workbench:** DatabasePanel moved here; connect /
  disconnect; not-queryable marking (AC-1,7,8).
- **D — Query surface:** strip to chat, rename tab (AC-9,10,11,12).
- **E — acceptance:** e2e_006 + extended fixtures; all boards green.

## Test strategy
Per `validation_method`: GWT acceptance (Playwright on fixtures + backend unit
for naming), deterministic (no live LLM — file Q&A scenario uses the canned
fixture path). mypy/ruff + frontend tsc/oxlint/build. All pre-existing boards
(001–005) must stay green.
