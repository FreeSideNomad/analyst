---
slug: semantic-depth
title: Semantic depth — PK/FK discovery + richer catalog to UI & planner
outcome: The catalog carries real meaning. Column meaning is derived from names + sampled data + type/cardinality; table meaning aggregates its columns AND its relationships. PK/FK relationships are discovered — declared (DB information_schema/SYSCAT) and IMPLIED by analysis (name heuristic + full referential-integrity validation) — with join semantics (inner vs left-outer when the FK is nullable). All of it is surfaced on table/column focus in the workbench, and fed into the query planner's prompt so it joins correctly.
status: done
merged_at: 2026-07-05
autonomy_level: high
assignee: local
owner: igormusic
area: profiling
roadmap_ref: pk-fk-relationship-discovery-validation
tracker_ref: local://semantic-depth
branch: semantic-depth
validation_method: "Unit tests for the implied-FK detector (RI holds / partial-overlap rejected / nullable → outer-join) against synthetic + Chinook data; GWT acceptance (Playwright on fixtures) for focus surfacing; planner cassette shows relationships in the prompt. Deterministic; live evals opt-in."
size: L
created: 2026-07-04
---

# Feature 009 — Semantic depth (PK/FK discovery + richer catalog → UI & planner)

> Confirmed with the human 2026-07-04. Bundles the four review threads. Sits
> **before** the query phases (007/008) — the planner needs relationships +
> richer semantics to write correct SQL. Roadmap item:
> `pk-fk-relationship-discovery-validation`.

## Scope

### 1. PK/FK discovery & validation
- **Declared** keys — from databases via `information_schema` / SYSCAT (already
  read in feature 005); surface them on the datasets.
- **Implied** foreign keys — heuristic + validated:
  - **Candidate** by name (`orders.customer_id` → `customers.id` /
    `customers.customer_id`), constrained to plausible type match.
  - **Referential integrity is REQUIRED** (human): every **non-null** FK value
    must exist in the referenced PK set — a true subset. Partial overlap →
    **rejected** (not a valid FK). Record the overlap as evidence.
  - **Nullable FK → outer join** (human): if the FK column has nulls, the
    relationship is optional; record `join_type = left_outer` so the planner
    LEFT-joins (never drops null-FK rows). Non-null FK → `inner`.
  - Record `declared | inferred`, the RI evidence, and the join type.
- Validation runs locally in DuckDB (aggregate/set queries), governance-safe.

### 2. Richer meaning derivation
- Column meaning derived from **name + sampled data + type/cardinality/
  distribution** (the reason we sample). Table meaning **aggregates** its
  columns AND its discovered relationships ("orders, one row per order, links to
  customers and products").
- Strengthen the cataloguer prompt/output so meaning isn't thin.

### 3. Surface on focus (workbench)
- Selecting a **table** or a **column** shows its meaning prominently:
  description, role, and **related-to** links (this column FK→ that table; this
  table is referenced by …), with declared/inferred + join-type shown.

### 4. Feed the planner
- The relationships (with join types), descriptions, and roles go into the
  **planner prompt** (`agentic/planner.py` / the CatalogPayload), so generated
  SQL joins on the right keys with the right join type. This is the point of the
  whole feature — it de-risks 007/008. Update `features/003-nl-qa/DESIGN.md`.

## Out
- The query result **table view** (>10-data-points default + toggle) — that is a
  small separate item folded into the query phases (007), not here.
- Editing/curating relationships by hand (later; ties to catalog editing).

## Dependencies
- Builds on 001 (profiler), 005 (declared keys), 006 (workbench focus UI).
- Precedes 007/008 (the planner consumes the relationships).

## Open questions (resolve in discover-acs)
- Composite FKs (multi-column) in v1, or single-column first?
- Cross-source implied FKs (a file column → a connected-DB table) — v1 or later?
