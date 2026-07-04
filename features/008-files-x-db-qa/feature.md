---
slug: files-x-db-qa
title: NL Q&A across files × one connected database (federation phase 3)
outcome: A user asks a plain-English question that joins their uploaded files with the tables of ONE connected database. The planner emits a SQL template with provider bindings; the runtime injects the file values (IN-list / VALUES, read-only, capped at N=100k) and runs the finished SELECT on the remote — the file's small side is pushed to the DB so its indexes do the join. Same trust trail (showing the template), result handling, and save-as-dataset as the other phases.
status: ready
autonomy_level: high
assignee: local
owner: igormusic
area: query
roadmap_ref: cross-dataset-joins-via-discovered-fks
tracker_ref: local://files-x-db-qa
branch: files-x-db-qa
validation_method: "GWT acceptance spec bound to Playwright + HTTP e2e on the fixtures API + Chinook golden DB; planner cassettes + opt-in live evals; live Docker DBs behind the `live` marker; unit tests for the dialect renderer + parameterized injection + cap."
size: L
created: 2026-07-04
---

# Feature 008 — NL Q&A across files × one connected database (phase 3)

> Federation phasing lives in `features/003-nl-qa/DESIGN.md` §4 + §6. This is
> **phase 3**: the full template + provider-binding + "always remotely" design.
> PIPELINE DEFERRED: run after phase 2 (feature 007).

## Scope (implements DESIGN §4)
- Planner emits `sql_template` + `bindings[]` (provider DuckDB query + `expand`
  hint) whenever a remote table is constrained by local file data — **never
  inline data**. The **LLM picks** `in_list` vs `values`.
- Runtime: run providers on DuckDB → **cap at N=100k (configurable)** → dialect
  render + **parameterize** → substitute → **run on the remote (read-only)**.
  Beyond N → an **explicit limitation** (no write path, no silent huge pull).
- Validation split: providers → C2 AST guard; remote template → read-only SELECT
  + parameterized injection.
- Trust trail shows the **unexpanded template**; result handling + save-as-dataset
  + download per DESIGN §5. Across-DB is composed via saved datasets, not planned.

## Out
- Across-DB (DB × DB) query planning — never; users compose via materialized
  results. Write-back to sources. Multi-remote in one query.

## Key references
- `features/003-nl-qa/DESIGN.md` — engine choice, "always remotely" federation,
  the template contract, cap/no-write, validation split, result handling.
- Depends on 007 (within-DB Q&A) + 006 (workbench) + 005 (connections).
