---
slug: charts-and-exports
checkpoint: 4
plan_status: approved  # in-session full-autonomy delegation (owner AFK), post-hoc review expected
created: 2026-07-15
---

# Plan — 014 charts & data exports

## Architecture

**Grounding facts (read this session):** an answer is built in `api/qa.py`
from an executed plan — `AnswerResult` carries `chart_type`
(bar/stat/none), `chart_data`, the full `table` block, and the trust trail
(which already discloses the executed SQL). Datasets are DuckDB views
(feature 013's overlay included), `store.fetch_all` reads them, and
`store.validation_problems` + `engine/sql_guard.assert_safe_select` already
gate arbitrary SELECTs. `openpyxl` is already a dependency (Excel
*reading*), `duckdb >= 1.5.4` does CSV/Parquet `COPY` natively.

### Components

1. **Domain — `src/analyst/domain/charts.py`** (pure):
   `SavedChart(chart_id, name, question, sql, chart_type, title, datasets)`
   + `UnknownChartError`, `ChartDataGoneError`. `chart_id` is a slug of the
   name + a counter (stable, human-readable).

2. **Engine — `src/analyst/engine/exports.py`**:
   - `export_dataset(store, name, fmt, path)` — CSV/Parquet via DuckDB
     `COPY (SELECT * FROM view) TO … (FORMAT …)`; Excel via openpyxl
     write-only mode streaming `fetch_all` rows. **No new dependencies; no
     network** (the DuckDB excel extension would need a download on first
     use — that breaks AC-11's offline mandate, so openpyxl writes Excel).
   - `export_query(store, sql, fmt, path)` — same, over a guarded SELECT
     (`assert_safe_select` + `validation_problems` first). **Uncapped by
     design** (AC-9): exports re-run the query with no display cap.
   - `DatasetStore.fetch_query(sql)` small addition if needed for uncapped
     reads through the engine layer.

3. **Answer interpretation extracted** — the result→chart logic in
   `api/qa.py` (stat vs bar, nice_max/ticks) moves to a shared
   `interpret_result(...)` (same module, importable), extended with **line
   inference**: first result column temporal (DATE/TIMESTAMP type or
   ISO-date-shaped strings) → `chart_type: "line"`. Q&A answers and saved
   chart opens render through the SAME function — one source of truth.

4. **Chart store — repository layer**: `charts.json` sidecar in the
   workspace data dir (exact 013 sidecar pattern). `StoreRepository` gains
   `charts()/save_chart()/open_chart()/rename_chart()/delete_chart()`.
   `open_chart` = validate stored SQL against the CURRENT store
   (`validation_problems`; dataset gone → `ChartDataGoneError`) → execute →
   `interpret_result` → AnswerResult-shaped payload with the stored trust
   trail. **No re-planning, no model** (AC-11). `FixtureRepository`: canned
   saved chart + in-memory CRUD for the browser flows.

5. **API — new `routes/charts.py`** (parallel-plan modularity):
   `GET /api/charts`, `POST /api/charts`, `GET /api/charts/{id}`,
   `PATCH /api/charts/{id}`, `DELETE /api/charts/{id}`,
   `GET /api/charts/{id}/export?format=csv|xlsx`; plus
   `GET /api/datasets/{name}/export?format=csv|parquet|xlsx` in
   `routes/datasets.py`. Unknown ids → 404; exports stream with a
   Content-Disposition filename.

6. **Frontend**: Save-as-chart control on answered results (inline name
   input); presentation override extended to line (SegmentedControl:
   chart type + table); a **Charts** nav area listing saved charts,
   opening one renders through the existing ResultCard machinery with the
   trust trail; Export buttons on the answer table view and the dataset
   detail (anchor to the export endpoints — browser handles the download).

### Key decisions

- **A saved chart persists the VALIDATED SQL + config, and re-runs on
  open** — the AC-5 anti-snapshot pin. Storing results would be simpler
  and wrong (stale, unbounded storage).
- **Excel via openpyxl, not the DuckDB excel extension** — the extension
  autoloads over the network on first use; offline behavior must be
  identical (AC-11). openpyxl is already in the tree.
- **One interpretation function for Q&A and charts** — line inference lands
  once and both surfaces inherit it; divergence is structurally impossible.
- **Exports run uncapped, display stays capped** — different purposes; the
  cap is a UI protection, not a data policy (AC-9).

## Charter Check

| Charter rule | Status | Evidence |
|---|---|---|
| Domain core pure | ✅ | `domain/charts.py` is dataclasses + errors |
| All DuckDB via engine layer | ✅ | COPY/fetch in `engine/exports.py`; repository calls engine only |
| Agentic prompts versioned | ✅ n/a | no model involvement; open_chart never re-plans |
| Rules/relationships never silently applied | ✅ n/a | no candidate-rule surface here; exports read the same views queries see (013 overlay included) |
| Governance: bulk data never to the model | ✅ | exports are engine-local file writes; nothing crosses |
| API thin | ✅ | routes delegate to repository/engine; schemas map |
| SQL safety | ✅ | stored SQL re-guarded on every open/export (`assert_safe_select` + `validation_problems`) |
| uv-only, typed, ruff | ✅ | no new deps |
| Autonomy stance | high (in-session delegation) matched by non-default validation_method (re-run pin + export fidelity + browser e2e) |
| Mutation policy | gates: (1) serve stored rows instead of re-running → AC-5 red; (2) cap the export path → AC-9 red; (3) drop SQL re-validation on open → dataset-gone scenario red |
| Performance budgets | below |

**Amendments:** none. No deviations.

## Phasing

1. **Chart lifecycle** — domain + sidecar CRUD + restart persistence; bind
   save/list/rename/delete/restart scenarios.
2. **Open/re-run** — interpret extraction + line inference + open path
   (incl. dataset-gone); bind inference/open/re-run/offline scenarios.
3. **Exports** — engine module + routes; bind the five export scenarios.
4. **Workbench** — save control, Charts area, override, export buttons,
   fixtures parity; bind the two browser scenarios; board 16/16.
5. **Harden** — the three mutation gates, lint/mypy/tsc, all boards, docs
   (README row + manual section).

## Performance budgets

- Save/rename/delete: sidecar JSON write, O(charts), instant.
- Open: one guarded SELECT + interpretation — same cost as asking the
  question, minus planning.
- Exports: DuckDB COPY streams; Excel writes row-streamed (openpyxl
  write-only). 1M rows × 10 cols: CSV/Parquet seconds-fast; Excel is the
  slow format by nature — acceptable, user-initiated.

## Collaboration schedule

Autonomous session; handoffs per checkpoint; owner reviews post-hoc via PR.
Stop-conditions: charter deviation or spec contradiction (none expected).

## Execution modes

Planner + implementer in-session under the standing delegation; PR
squash-merge at the end.

## Test strategy

Per `validation_method`: the 16-scenario board is the WHAT-gate — AC-5
pinned by an actual refresh-then-reopen round trip, AC-9 by a
display-capped result whose file is complete, AC-8 cross-checked against a
013-normalized view. Unit stream: chart store CRUD + sidecar round-trip,
interpret extraction (stat/bar/line boundaries, temporal detection), export
writers per format (headers + rows + row counts), route status codes.
Mutation gates as named in the Charter Check. Browser e2e covers save/open/
override against seeded fixtures. Fully offline; no cassettes needed
(no planning anywhere in this feature).
