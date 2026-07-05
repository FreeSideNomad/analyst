---
slug: within-db-qa
title: NL Q&A within a single connected database (federation phase 2)
outcome: A user asks a plain-English question about the tables of ONE connected database and gets a confidence-gated answer — the generated SELECT runs entirely on that remote (read-only), with the same trust trail as file Q&A. Small results are interpreted; larger results return as a paginated table that can be saved as a dataset or downloaded. No file×DB joins yet (that is phase 3 / feature 008).
status: done
merged_at: 2026-07-05
autonomy_level: high
assignee: local
owner: igormusic
area: query
roadmap_ref: cross-dataset-joins-via-discovered-fks
tracker_ref: local://within-db-qa
branch: within-db-qa
validation_method: "GWT acceptance spec bound to Playwright + HTTP e2e on the fixtures API and the Chinook golden DB (deterministic); planner uses recorded-real cassettes + opt-in live evals; live Docker DBs behind the `live` marker."
size: L
created: 2026-07-04
---

# Feature 007 — NL Q&A within one connected database (phase 2)

> Federation phasing lives in `features/003-nl-qa/DESIGN.md` §6. This is
> **phase 2**: querying the tables of ONE remote DB, no file involvement.
> PIPELINE DEFERRED: run after the workbench (006) and the hardening land.

## Scope
- Route an NL question scoped to a single connected database to the planner; the
  generated **single read-only SELECT runs on that remote** (via the scanner for
  PG/SQLite; the driver bridge for MSSQL/DB2). No cross-source, so **no template
  bindings** (that is phase 3).
- Reuse feature-003 confidence gating, clarify/abstain, and the trust trail.
- **Result handling** per DESIGN §5: ≤ ~10 rows → interpreted answer; above →
  paginated `table` result with **Save as dataset** (materialize to the store,
  profiled, with provenance) + **Download**.
- Read-only throughout; the remote query is bounded by the user's DB permissions.

## Out
- File × DB joins (phase 3 / feature 008). Across-DB (never — composed via saved
  datasets). Write-back to sources.

## Key references
- `features/003-nl-qa/DESIGN.md` — the consolidated Query & Federation design
  (engine choice, result handling, provenance, validation split).
- Depends on 005 (DB connections) + 006 (workbench surfaces DB tables).
