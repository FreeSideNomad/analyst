---
slug: "2026-07-18-curation-500-transient-sdk"
title: "Answering a clarification intermittently 500s (transient SDK max-turns error unwrapped)"
severity: high
blocks_user: true
workaround: "resubmit the answer (the catalog is untouched by the failure)"
status: closed
resolution: fixed

source:
  kind: user-report
  ref: "2026-07-18 owner testing curation on messy_sales.csv — 500 on /curation/answer with 'Something else: CAD'"

repro: |
  1. Live mode (container). Answer a catalog clarification.
  2. Intermittently the Claude Agent SDK dies with "Claude Code returned an
     error result: Reached maximum number of turns (1)" on a single-turn
     request; the raw Exception is unmapped -> 500 Internal Server Error.

expected: "Any completion failure is reported plainly (502, 'nothing was changed — try again'); the catalog stays untouched."
actual: "Raw 500; catalog untouched (that invariant held) but the failure was not plain."

feature_refs:
  - "features/016-catalog-curation"

investigation:
  match_mode: auto
  candidates_considered: 1

pin_confirmation:
  feature_refs:
    - feature: "features/016-catalog-curation"
      spec_path: "tests/unit/test_curation.py"
      red_run:
        result: red
        command: "uv run pytest tests/unit/test_curation.py -k 'crash or retries'"
        output: "3 failed before the fix (raw Exception from curator; 500 from route; no retry); 16 passed after"

fix_commits: []  # committed with this artifact
harden_results:
  mutation_score: 1.0  # removing the retry -> retry test red; removing the wrap -> 502 test red
  arch_check: "pass (boundary wrapping in agentic layer + one repository guard; assembler hardened identically)"
  bug_line_mutation_confirmed: true

gap_analysis:
  - category: incomplete_spec
    phase: atdd
    finding: "AC-12's 'failed completion' scenario was pinned with a CurationError-raising stub — the one failure type already handled. Raw backend/SDK exceptions (the realistic failure) had no pin, so the 500 path shipped untested."
    followup_kind: add_verification
  - category: inadequate_verification
    phase: harden
    finding: "The transient max-turns SDK error was OBSERVED during cassette recording and retried by hand instead of being treated as a signal that production needed the same retry."
    followup_kind: add_verification
followups:
  - category: incomplete_spec
    action: "Route-level pin: raw-exception curator -> 502 plain message, catalog byte-identical; same wrap for the dashboards assembler"
    status: applied
  - category: inadequate_verification
    action: "One retry for the known-transient SDK error in ClaudeAgentBackend (benefits cataloguing, curation, planning, and assembly alike), pinned by a flaky-once unit test"
    status: applied
---

# Curation 500 on transient SDK failure

The lesson: when a flake appears during recording sessions, production has
the same flake — absorb it where it originates (one backend retry) AND make
every boundary fail plainly regardless.
