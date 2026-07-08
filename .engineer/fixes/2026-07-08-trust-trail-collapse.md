---
slug: "2026-07-08-trust-trail-collapse"
title: "Trust trail panel collapses by itself right after opening"
severity: medium
blocks_user: false
workaround: "click Trust trail again (it may snap closed repeatedly while an answer is fresh)"
status: gap-analyzed  # terminal here: validator's 'closed' requires a red fix-pin, which a not-reproducible defect cannot honestly have
resolution: not-reproducible  # app behaves correctly; the observing script caused it

source:
  kind: internal
  ref: "2026-07-06 manual-screenshot session — Playwright needed a retry-click loop to keep the trail open"

repro: |
  1. Run the app (observed in fixtures mode; suspected mode-independent).
  2. Ask "What is the revenue by region?" and answer the clarification.
  3. When the answer renders, click "Trust trail" to expand it.
  4. Within ~a second the panel snaps closed again.

expected: "The trust trail stays open until the user closes it."
actual: "The panel collapses on its own shortly after opening (intermittent, reliably reproducible right after an answer arrives)."

feature_refs:
  - "features/003-nl-qa"

investigation:
  match_mode: auto
  candidates_considered: 1

pin_confirmation:
  feature_refs:
    - feature: "features/003-nl-qa"
      spec_path: "features/003-nl-qa/spec.md"  # behavior-pin scenario added (not a red-first fix pin — defect not reproducible)
      red_run:
        result: n/a-behavior-pin
        command: "uv run pytest features/003-nl-qa/.build/generated -k arrives_expanded"
        output: "GREEN on current code by design; RED when the pinned behavior (defaultOpen on latest answer) is mutated away — mutation gate verified 2026-07-08"

fix_commits: []  # no product code changed — behavior pin + versioned capture script only

harden_results:
  mutation_score: 1.0  # single-behavior gate: defaultOpen removal -> pin RED; restore -> GREEN (13/13)
  arch_check: "pass (no product code touched)"
  bug_line_mutation_confirmed: true

gap_analysis:
  - category: incomplete_spec
    phase: atdd
    finding: "Feature 003's board implicitly depended on the trail's default-open behavior (a step clicks the SQL tab without ever opening the trail) but no scenario stated it — so a script author reasonably assumed the trail starts closed, toggled it, and misread the toggles as a self-collapse bug."
    followup_kind: extend_spec
  - category: inadequate_verification
    phase: verify
    finding: "The screenshot capture tool lived unversioned in a session scratchpad and clicked UI state into being instead of asserting it; its false observations were reported as a product bug."
    followup_kind: add_verification

followups:
  - category: incomplete_spec
    action: "Add an explicit 'trust trail arrives expanded and stays expanded' scenario to features/003-nl-qa/spec.md with e2e bindings"
    status: applied
  - category: inadequate_verification
    action: "Version the manual screenshot tool as scripts/capture_screenshots.py, asserting (never clicking into) UI state, with the default-open note inline"
    status: applied
---

# Trust trail collapses right after opening

## Investigation (2026-07-08) — NOT REPRODUCIBLE; remount theory DISPROVEN

Two instrumented Playwright probes against the exact build and flow from the
2026-07-06 screenshot session (fixtures app, same viewport/scale):

1. **Remount probe** — marked the trail's DOM node (`dataset.probe`) after
   the answer arrived, sampled for 4s: the node was never replaced
   (`marker=1` throughout) and the panel stayed OPEN the whole time. No
   poll-driven remount exists; the catalog poll re-renders but never
   remounts (message keys `m.id` are stable, `nid()` is monotonic).
2. **Sequence probe** — replayed the capture script's exact steps
   (answer → SQL tab → Assumptions tab) with 250ms state sampling: the
   trail was open by default (`defaultOpen={isLast}` works — `lastResultId`
   derives from `messages` in the same render, no race), tab switches never
   closed it, and it remained open across 1.5s of sampling.

## Root cause of the 2026-07-06 observations

The trail **opens by default** on the latest answer. The screenshot script
assumed it started closed and clicked "Trust trail" to "open" it — the
click **closed** the already-open panel. Every "collapsed" frame in that
session immediately followed one of the script's own toggle clicks; the
subsequent waits then timed out against a panel the script itself had
closed, which read as "collapses by itself." The retry-click loop
compounded it (each retry toggled state again).

Defect location: the automation script, not the application.
