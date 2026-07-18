---
ac_count: 13
high_priority_count: 8
discovered: 2026-07-15
mode: greenfield
status: approved (blanket in-session delegation, 2026-07-18 — owner: "work autonomously, assume everything approved")
note: >
  Drafted 2026-07-15 and held at the review gate; approved 2026-07-18
  under the owner's blanket delegation ("assume everything approved").
---

# Acceptance criteria — 015 interactive dashboards (PROPOSED)

Scope decisions proposed for review:

- **A dashboard is a named grid of widgets; a widget IS a feature-014 saved
  chart** plus a layout slot. Everything a saved chart guarantees (re-run
  on open, trust trail, presentation switch) is inherited, not rebuilt.
- **The agent authors; the engine executes.** The model produces a
  dashboard SPEC (widgets, their questions/SQL, filterable dimensions,
  layout) — metadata only, validated like any plan; every number is
  computed locally.
- **Authoring needs the model; viewing does not.** An existing dashboard
  opens and filters fully offline. With no AI configured, dashboard
  creation says so plainly (the catalog-off pattern).
- **v1 filters** are equality/date-range on agent-chosen dimensions,
  applied to every widget whose data carries that dimension; widgets
  without it visibly say "not filtered".
- Deferred (explicitly OUT of v1, next slices): dashboard sharing/export
  as PDF, auto-refresh schedules, per-widget manual SQL editing.

## AC-1: A plain-English request assembles a dashboard (High)
"Build me a sales overview dashboard" produces a named dashboard with
several relevant widgets (e.g. revenue by region, trend over time, top
customers), each rendered from locally executed queries over the workspace.

## AC-2: Ambiguity triggers AskQuestion, not guessing (High)
When the request is under-specified (which amount? which time grain?), the
agent asks a structured clarification before assembling — same primitive
as Q&A.

## AC-3: Every widget carries its trust trail (High)
Each widget exposes assumptions, lineage, and the exact SQL behind it —
the same trail contract as answers and saved charts.

## AC-4: A shared filter re-scopes every widget (High)
Setting the dashboard's filter (e.g. region = "East", or a date range)
re-runs the widgets and their numbers change accordingly; clearing it
restores the originals. Widgets lacking the filtered dimension indicate
they are unaffected.

## AC-5: Clicking a chart cross-filters the others (High)
Clicking a category in one widget applies it as a dashboard filter; the
other widgets update, the active filter is visible, and it is clearable
in one action.

## AC-6: Presentation stays switchable per widget (Medium)
Each charted widget switches between bar/line/table without affecting the
others.

## AC-7: Drill-down opens the underlying rows (Medium)
From a widget, the user opens the rows behind the aggregate (capped table
view, exportable via feature 014).

## AC-8: Dashboards are edited conversationally (High)
"Add a widget showing average order value by month" adds it; removing and
rearranging widgets is possible; edits go through the same clarify-first
agent flow.

## AC-9: Dashboards persist and re-run live (High)
Named dashboards are listed per workspace, survive a restart, and opening
one re-runs every widget against current data — never snapshots.

## AC-10: A broken widget fails alone, clearly (Medium)
If one widget's dataset is gone, that widget shows a plain "its data is
gone" state; the rest of the dashboard renders and the widget can be
removed.

## AC-11: Viewing is local; authoring degrades honestly (High)
Opening/filtering an existing dashboard runs fully offline with no model
calls. Creating/editing with no AI configured fails with a clear message
(never a silent hang).

## AC-12: Governance holds (High)
Only schema/profiles/catalog metadata and the dashboard spec cross to the
model; widget SQL is validated and guarded exactly like Q&A plans; all
execution is local DuckDB.

## AC-13: Errors are clean (folded) (Medium)
Opening/renaming/deleting an unknown dashboard fails with a clear
not-found; malformed agent specs are rejected with the reason (never a
half-assembled dashboard).
