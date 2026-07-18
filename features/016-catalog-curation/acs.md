---
ac_count: 12
high_priority_count: 8
discovered: 2026-07-18
mode: greenfield
---

# Acceptance criteria — 016 catalog curation

## AC-1: A clarification is a real form (High · happy-path)
A "Needs review" clarification presents its options as selectable choices
plus a free-form "Something else" field; exactly one can be chosen and
submitted. (Today they are display-only chips.)

## AC-2: Answering with an option completes the analysis (High · happy-path)
Submitting a chosen option updates the column's description to state the
settled meaning (agent-synthesized, evidence + answer as ground truth) and
the clarification disappears.

## AC-3: A free-form answer is equally authoritative (High · happy-path)
Submitting "Something else" text produces the same completion, with the
user's wording reflected in the settled description.

## AC-4: The blast radius is bounded (High · invariant)
Answering or correcting changes AT MOST the affected column's description
and its own table's description. No other table's catalog entry changes —
verified, not assumed.

## AC-5: Curation is recorded as provenance (Medium · cross-cutting)
A settled entry is visibly human-confirmed (badge) and carries what was
answered/suggested; the raw agent-only state is distinguishable from the
curated state.

## AC-6: Human-settled meanings are sticky (High · invariant)
Automatic re-cataloguing — a data refresh, retroactive re-derivation from
new relationships, a restart — never overwrites a human-settled
description. Only a new human curation may change it.

## AC-7: Any description accepts a suggested correction (High · happy-path)
Every column and table description offers "suggest a correction"; the
user's note is treated as authoritative and the agent re-synthesizes the
description(s) within the AC-4 blast radius, marked human-confirmed.

## AC-8: Offline curation degrades honestly (Medium · cross-cutting)
With no AI configured, a correction applies the user's words verbatim
(sticky, badged, marked for later reconciliation) and a clarification
answer records the choice and applies a plain templated update — never a
silent failure, never a hang.

## AC-9: Settled meanings sharpen Q&A (Medium · happy-path)
After settling an ambiguous column's meaning, a question that depends on
that meaning is answered using the settled interpretation (the planner
reads the curated catalog).

## AC-10: The workbench carries the flows (Medium · browser)
The clarification form and the correction affordance work in the workbench
without a page reload, and the human-confirmed badge appears immediately.

## AC-11: Governance holds (High · structural)
Only profile metadata, existing catalog text, and the user's answer cross
to the model — never bulk rows; the prompt is a versioned artifact and the
exchange is cassette-recordable.

## AC-12: Errors are clean (folded) (Medium · error)
Submitting an empty answer is rejected with a message; answering a
clarification that no longer exists fails clearly as not-found; a failed
agent call leaves the catalog unchanged and says so.
