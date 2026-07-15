---
slug: data-normalization-detection
title: Data normalization detection — propose, validate, apply
outcome: Ingested data with inconsistent value representations (case variants like "East"/"east"/"EAST", stray whitespace, near-duplicate category labels) is DETECTED at profiling time; the app proposes explicit normalization rules in plain language, the user approves or rejects them (never silently applied — charter rule), and approved rules materialize as a normalized view of the dataset that querying and cataloguing use. Rules are inspectable and reversible; the raw data is never mutated.
status: ready
autonomy_level: high
assignee: local
owner: igormusic
area: profiling
roadmap_ref: data-normalization-detection
tracker_ref: local://data-normalization-detection
branch: data-normalization-detection
validation_method: "Acceptance board over messy fixture CSVs (case variants, whitespace, near-duplicates): detection surfaces proposals; approval materializes a normalized view queryable via NL Q&A; rejection leaves data untouched; raw values always recoverable. Mutation gate on the detector and the never-silently-applied invariant. Browser e2e for the approve/reject flow."
size: M
created: 2026-07-15
---

# Feature 013 — Data normalization detection

> Promoted from roadmap item `data-normalization-detection` (horizon: next).
> Autonomous session 2026-07-15: full autonomy delegated in-session by the
> owner (AFK); checkpoint decisions recorded in handoffs.

Roadmap note: "Detect normalization needs (case standardization
upper/lower/proper, etc.) and propose rules."

Charter anchors:
- Agentic layer owns "normalization detection (case standardization —
  upper/lower/proper — and beyond)".
- **"Discovered relationships and normalization rules are test-validated
  candidates, never silently applied — a wrong join corrupts every
  downstream answer."** The approval gate is a hard requirement, not UX
  polish.
- Clarifications flow through the AskQuestion primitive when confidence is
  low.

Scope sketch (to be fixed at discover-acs):
- Detection during/after profiling: per-column findings (case variants of
  the same value, leading/trailing whitespace, mixed separators) with
  evidence (the variant groups and their counts).
- Proposals as explicit rules ("standardize `region` to Proper case —
  merges 3 variants of 4 values"), approve/reject per rule.
- Application: normalized VIEW (raw Parquet untouched), reflected in
  profiles/catalog/query; reversible by revoking the rule.
