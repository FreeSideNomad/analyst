---
slug: dashboards
checkpoint: 4
plan_status: approved  # blanket in-session delegation (owner AFK, "assume everything approved")
created: 2026-07-18
---

# Plan — 015 interactive dashboards

## Architecture

**The composition thesis:** a dashboard widget IS a feature-014 saved-chart
shape (question + validated SQL + presentation + trust trail) plus a layout
slot; rendering reuses `shape_answer`/`AnswerBody` wholesale. What is NEW is
(a) agent authoring of a multi-widget SPEC, and (b) the filter machinery.

### Components

1. **Domain — `src/analyst/domain/dashboards.py`** (pure):
   `DashboardWidget(widget_id, question, sql, chart_type, title, source,
   assumptions, lineage)`, `DashboardFilter(column, label)`,
   `Dashboard(dashboard_id, name, widgets, filters)` + `UnknownDashboardError`.
   `source` names the widget's underlying dataset (drill-down target).

2. **The filter mechanism — a SQL marker, validated twice.** Every widget
   SQL must contain the literal marker `/*FILTERS*/` inside its WHERE
   clause (the authoring prompt mandates `WHERE /*FILTERS*/ 1=1` before
   any GROUP BY). Applying filters = substituting the marker with
   `("col" = 'value') AND` clauses (values SQL-escaped by the engine
   helper), then re-guarding the final SELECT (`assert_safe_select` +
   `validation_problems`) before execution. A spec whose widget SQL lacks
   the marker or fails validation is rejected WHOLE — no half-assembled
   dashboards (AC-13). Filters therefore re-scope *before aggregation*,
   which is the only semantically correct place.

3. **Agent authoring — `src/analyst/agentic/dashboards.py`** (versioned
   prompt, structured output): input = the same metadata the Q&A planner
   sees (tables/columns/descriptions via `query_table_from_summary`) +
   the user's request (+ the current dashboard spec when editing). Output =
   `{name, widgets: [{question, sql, chart_type, title, source}],
   filters: [{column, label}]}` OR `{clarification: {question, options}}`
   (AC-2, AskQuestion). Runs through `LLMGateway` — cassette
   `tests/cassettes/dashboards.json` recorded live once. The gateway
   payload is metadata-only (AC-12 pinned by a prompt-spy scenario).

4. **Repository (`StoreRepository`)** — sidecar `dashboards.json`
   (established pattern): `dashboards()`, `create_dashboard(request)`
   (agent assemble → validate every widget → persist; clarification
   passes through; no curator/assembler configured → clear error, AC-11),
   `edit_dashboard(id, request)` (same, seeded with the current spec),
   `run_dashboard(id, filters)` → per-widget `shape_answer` results (a
   widget whose SQL no longer validates yields a per-widget data-gone
   payload, AC-10), `drill_dashboard(id, widget_id, filters)` (SELECT *
   FROM source with the same filter clauses, display-capped),
   `rename/delete`. `FixtureRepository`: one canned dashboard + canned
   assemble/edit so the browser flows run.

5. **API — `routes/dashboards.py`**: CRUD + `POST /api/dashboards`
   (assemble | clarification), `POST /api/dashboards/{id}/run` (filters in
   body), `POST /api/dashboards/{id}/edit`,
   `GET /api/dashboards/{id}/widgets/{wid}/drill?…`. 404/400/502 mapping
   as established.

6. **Frontend — `DashboardsPage`** (nav peer of Charts): NL request box →
   grid of widgets rendered via `AnswerBody` (trust trail included),
   filter bar (chips, one-click clear), bar-click → cross-filter chip,
   drill modal (ResultTableView), edit box, AskQuestion card for
   clarifications, per-widget unaffected note when a filter's column is
   absent from the widget's source.

### Key decisions

- **Filter-by-marker, not post-hoc WHERE on results** — filters must apply
  before aggregation; the marker makes that explicit, mechanical, and
  re-validated. Rejecting marker-less specs keeps the guarantee whole.
- **Widget = saved-chart shape** — rendering, trails, presentation
  switching, and future features come free; no second chart pipeline.
- **Reject-whole on invalid specs** — a dashboard with a broken widget at
  BIRTH is a lie; a dashboard whose widget breaks LATER (dataset deleted)
  degrades per-widget. Different failure classes, different behavior.
- **Viewing is model-free** — run/filters/drill execute stored SQL only;
  the model touches nothing after assembly (AC-11).

## Charter Check

| Charter rule | Status | Evidence |
|---|---|---|
| Domain pure | ✅ | dataclasses + error only |
| DuckDB via engine | ✅ | execution via engine.query/run_select + engine-quoted filter clauses |
| Agentic prompts versioned + structured | ✅ | agentic/dashboards.py; cassette-recorded |
| AskQuestion on low confidence | ✅ | clarification output path (AC-2) |
| Governance | ✅ | assembly payload metadata-only; prompt-spy scenario pins it |
| Never half-applied | ✅ | reject-whole on invalid specs |
| API thin | ✅ | routes delegate |
| Autonomy | high (blanket delegation) + validation_method gates |
| Mutation policy | gates: (1) filter marker ignored at run → AC-4 red; (2) accept marker-less spec → AC-13 red; (3) run-time SQL guard dropped → filter-injection unit red |
| Performance | below |

**Amendments:** none.

## Phasing

1. Domain + filter substitution + run/drill over a HAND-BUILT dashboard
   (no agent): viewing/filtering/persistence/broken-widget scenarios.
2. Agent authoring module + cassette recording + create/edit paths:
   assembly/clarify/edit/governance/reject scenarios.
3. Routes + fixture parity.
4. DashboardsPage UI + browser scenarios; board 15/15.
5. Harden: mutation gates, sweep, docs.

## Performance budgets

Run = N widget SELECTs (N small, display-capped results); filter change =
same cost; assembly = one model call. All interactive-latency local.

## Collaboration schedule / Execution modes

Autonomous under the blanket delegation; handoffs per checkpoint; PR at
the end.

## Test strategy

Board: 13 in-process + 2 browser; agent turns replay
`tests/cassettes/dashboards.json`. Units: filter substitution + escaping +
re-guarding (injection attempts!), marker validation, sidecar round-trip,
per-widget failure isolation, route codes. Mutation gates as listed.
