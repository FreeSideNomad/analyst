---
slug: "2026-07-15-profiler-alias-collision"
title: "Profiling fails on datasets with a column literally named 'v' (or 'c')"
severity: medium
blocks_user: true
workaround: "rename the column before ingesting"
status: closed
resolution: fixed

source:
  kind: internal
  ref: "found 2026-07-15 while building feature 014 export tests (fixture columns k,v); captured to .engineer/inbox.md"

repro: |
  1. Ingest any CSV containing a column named exactly "v" (e.g. header "k,v").
  2. Ingestion errors during profiling: Binder Error — column "k" must appear
     in the GROUP BY clause (the top-K distribution SQL's alias "AS v" is
     shadowed by the real column: GROUP BY v binds to t.v, not the alias).

expected: "Any legal column name profiles fine; internal SQL aliases never collide with user data."
actual: "Datasets with a column named 'v' (and analogously 'c') fail ingestion at the profiling step."

feature_refs:
  - "features/001-file-ingestion-and-profiling"

investigation:
  match_mode: auto
  candidates_considered: 1

pin_confirmation:
  feature_refs:
    - feature: "features/001-file-ingestion-and-profiling"
      spec_path: "tests/unit/test_profiler.py"
      red_run:
        result: red
        command: "uv run pytest tests/unit/test_profiler.py -k aliases"
        output: "FAILED test_columns_named_after_sql_aliases_profile_fine (BinderException) before the fix; 13 passed after"

fix_commits: []  # committed with this artifact — positional GROUP BY 1 / ORDER BY 2 in engine/profiler.py

harden_results:
  mutation_score: 1.0  # reverting to alias-name grouping -> pin RED
  arch_check: "pass (engine-internal one-liner)"
  bug_line_mutation_confirmed: true

gap_analysis:
  - category: inadequate_verification
    phase: implement
    finding: "Internal SQL used unqualified alias names in GROUP BY/ORDER BY; nothing exercised profiling against adversarial column names (single-letter names shadowing aliases)."
    followup_kind: add_verification
followups:
  - category: inadequate_verification
    action: "Regression test with columns named exactly 'v' and 'c' (the aliases used); positional GROUP BY/ORDER BY in the profiler"
    status: applied
---

# Profiler alias collision

DuckDB resolves `GROUP BY v` to a real column `v` over a SELECT alias `v`.
The top-K distribution query aliased its expressions as `v`/`c`, so any
dataset carrying those column names failed profiling entirely. Fix:
positional `GROUP BY 1 ORDER BY 2 DESC, 1` — immune to every column name.
