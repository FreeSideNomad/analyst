---
slug: data-workbench-ux
title: Two-surface UX — data workbench (Ingest & Profile) + pure Query
outcome: The app collapses to two surfaces. "Ingest & Profile" becomes the data workbench — add data (upload files AND connect databases), then browse everything as a source-grouped tree (Files / Databases → tables → columns) showing profile stats + the semantic catalog (descriptions, roles, needs-review) + per-column drilldown. "Query" is renamed from "Catalog & Q&A" and stripped to the chat only. Datasets get a unified source.entity.ext naming scheme grouped by source.
status: done
merged_at: 2026-07-04
autonomy_level: high
assignee: local
owner: igormusic
area: frontend
roadmap_ref: react-tailwind-shadcn-frontend-app-shell
tracker_ref: local://data-workbench-ux
branch: data-workbench-ux
validation_method: "GWT acceptance spec bound to Playwright e2e on the fixtures API (deterministic); backend unit tests for the naming scheme; frontend lint/typecheck/build."
size: L
created: 2026-07-04
---

# Feature 006 — Two-surface UX: data workbench + pure Query

> Requirements CONFIRMED with the human 2026-07-04 (see the four decisions
> below). PIPELINE DEFERRED: run discover-acs → atdd → plan → implement only
> AFTER the hardening PR #6 merges, so DB tables are actually queryable (H5).

## Confirmed decisions

1. **Single-table files** (CSV/TSV/JSON) named `file.ext`, shown as a **group
   of one** — the "group by first segment" rule is uniform across all sources.
2. **Left rail** has **two top-level sections: Files / Databases**, each with
   its groups → tables → columns.
3. **Query tab** is **chat only** — no dataset indicator, no metadata, no
   drilldown.
4. **Sequencing**: this is a **new feature after PR #6 merges** (not interleaved
   with hardening).

## Scope

**Ingest & Profile (the workbench):**
- Add data: upload files (existing) **+ connect a database** — the
  connect/list/detach UI moves here (the `/api/databases` endpoints already
  exist; the CatalogTree "Connect a database — soon" placeholder becomes real).
- Browse: a source-grouped tree — **Files** and **Databases** sections →
  group-by-first-segment → tables → columns.
- Detail: for a selected table, show profile stats **and** the semantic catalog
  (table description; per-column description + role; "needs review"
  clarifications) — the metadata currently on the Workspace view.
- **Column drilldown** (the current ColumnDetail pane) lives here, enriched with
  the profile stats (min/max/quantiles/samples/null rate/distinct).

**Query (renamed from "Catalog & Q&A"):**
- The chat only. No catalog tree, no ColumnDetail, no scope indicator.

**Unified dataset naming** (`source.entity.ext`, group by first segment):

| Source | Name | Group |
|---|---|---|
| Excel | `company.employees.xlsx` | `company` |
| CSV/TSV/JSON | `orders.csv` | `orders` (group of one) |
| Database | `sales_db.orders` | `sales_db` |

Sanitize per-segment (preserve the dot separators); update the Excel/CSV
ingestion naming; DB naming (`conn.table`) already fits.

## Dependencies & flags
- **Depends on H5** (federated Q&A, harden-wave1 follow-up): DB-table tables
  will display/profile/catalog here regardless, but NL Q&A over them only works
  once H5 lands.
- Backend naming change alters dataset IDs (wire contract) — pre-release, OK;
  the planner sees dotted view names (the C2 AST guard already handles them).

## Open question (resolve in discover-acs)
- Catalog **editing** ("grab the wheel" per the vision) — is the semantic layer
  editable on Ingest & Profile in this feature, or display-only for now?
