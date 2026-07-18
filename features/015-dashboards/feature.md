---
slug: dashboards
title: Interactive dashboards — agent-authored, filterable, widget-composed
outcome: A user describes the dashboard they want in plain English and the agent assembles it as a grid of widgets — each widget a saved chart (feature 014's unit) with its trust trail intact. The dashboard is then genuinely interactive — a shared filter bar (e.g. date range, region) re-scopes every widget, clicking a chart segment cross-filters the others, chart types remain switchable per widget, and drill-down opens the underlying rows. Dashboards are named, listed, editable (add/remove/rearrange widgets via the agentic AskQuestion workflow), persist per workspace, and every number on screen remains locally computed with an inspectable trail.
status: ready
autonomy_level: high
assignee: local
owner: igormusic
area: output
roadmap_ref: exports-visualizations-dashboards
tracker_ref: local://dashboards
branch: dashboards
validation_method: "Acceptance board over fixture + real-store data: NL request assembles a multi-widget dashboard (cassette-replayed agent turn); shared filter re-scopes all widgets (numbers verified); cross-filter click propagates; persistence across restart; browser e2e for assemble/filter/drill flows. Mutation gates on filter propagation and widget-trail integrity."
size: L
created: 2026-07-15
---

# Feature 015 — Interactive dashboards

> Promoted from roadmap item `exports-visualizations-dashboards` (later/p2)
> now that its building block shipped: a dashboard widget IS a feature-014
> saved chart. Roadmap note: "Tableau-like: agent assembles a multi-widget
> dashboard from an NL request, then fully interactive (filters,
> cross-filtering, chart-type switching, drill-down). Built/refined via the
> agentic AskQuestion workflow. Each widget keeps its trust trail; queries
> run locally in DuckDB."

Charter anchors: dashboards are named core scope; the agentic layer owns
dashboard authoring (prompt-driven, versioned prompts, AskQuestion on low
confidence); governance invariant unchanged (the model sees metadata and
the dashboard *spec*, never bulk rows; all widget queries run locally).

Initialized during the 2026-07-15 autonomous session. **AC discovery is
flagged for owner review** (see the CP2 handoff) — this is the largest
product-taste surface so far; the standing delegation was deliberately NOT
used to self-approve the AC contract.
