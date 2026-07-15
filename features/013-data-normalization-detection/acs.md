---
ac_count: 12
high_priority_count: 8
discovered: 2026-07-15
mode: greenfield
note: >
  Autonomous session (owner AFK, full autonomy delegated in-session).
  The four interview passes were self-answered from feature.md, the charter,
  and the roadmap note; decisions recorded here and in the CP2 handoff.
---

# Acceptance criteria — 013 data normalization detection

Scope decisions (recorded in lieu of the interview):

- **v1 detects representation inconsistencies that are provably the same
  value**: letter-case variants, leading/trailing whitespace, and repeated
  internal whitespace. Fuzzy near-duplicates (typos, abbreviations) are OUT —
  they need judgment and belong to a later slice.
- **v1 covers file-backed datasets.** Connected-database tables are out of
  scope (they are external systems of record; standardizing them locally is
  a different conversation).
- **Detection is fully local and deterministic** — no model calls; it must
  work identically in an offline deployment.
- The **original data is never mutated**; standardization is a reversible
  overlay the user controls.

## AC-1: Case variants of the same value are detected

Priority: High · Type: happy-path

When an ingested file's text column holds the same value in different
letter cases (e.g. "East", "east", "EAST"), profiling surfaces a
normalization finding for that column, showing each group of variants
together with how many rows carry each variant.

## AC-2: Whitespace inconsistencies are detected

Priority: High · Type: happy-path

Values that differ only by leading/trailing whitespace or by repeated
spaces inside (e.g. " East", "New  York") are detected as variants of the
same value and reported the same way.

## AC-3: Clean columns produce no proposals

Priority: High · Type: edge-case

A column whose values are already consistent yields no normalization
finding — the feature must not manufacture busywork or noise.

## AC-4: Proposals are explicit, plain-language rules

Priority: High · Type: happy-path

Each finding comes with a proposed rule stated in domain language — which
column, what standardization (e.g. "Proper case, trimmed"), and its effect
("merges 3 variants of 'east' covering 41 rows") — precise enough to judge
without seeing any code.

## AC-5: Proposals are never silently applied

Priority: High · Type: error/invariant (charter)

Until a person approves a rule, the dataset behaves exactly as ingested:
queries, the profile, and the catalog all show the original values, even
while proposals are pending. (Charter: "normalization rules are
test-validated candidates, never silently applied.")

## AC-6: Approving a rule standardizes what queries see

Priority: High · Type: happy-path

After a rule is approved, questions asked of that dataset see the
standardized values — e.g. "total amount by region" returns one "East"
group where three case variants existed before.

## AC-7: The original values are preserved and the rule is reversible

Priority: High · Type: cross-cutting

Approval never rewrites the ingested data: the original values remain
recoverable, and revoking an approved rule returns queries to the original
values — no re-ingest required.

## AC-8: A rejected proposal stays rejected

Priority: Medium · Type: edge-case

Dismissing a proposal removes it, and the same finding is not re-proposed
for that dataset on later profiling or after a restart.

## AC-9: The profile reflects an approved standardization

Priority: Medium · Type: happy-path

Once a rule is approved, the column's profile tells the truth about the
standardized data — the variant groups collapse (distinct count drops, the
merged value's row count is the sum of its variants).

## AC-10: Approved rules survive a restart

Priority: High · Type: cross-cutting

After the app restarts, previously approved rules are still in effect —
queries see standardized values without anyone re-approving anything.

## AC-11: The workbench carries the approve/dismiss flow

Priority: Medium · Type: happy-path (browser)

In the data workbench, a column with findings visibly indicates pending
proposals; opening it shows each proposal's plain-language rule and
evidence with approve and dismiss actions, and acting on one updates the
view without a page reload.

## AC-12: Detection stays local and stays in its lane

Priority: High · Type: cross-cutting/governance

Detection and application run fully locally with no model calls (identical
behavior in an offline deployment), and only text-like columns are
examined — numeric, date, and identifier-like columns (near-unique values)
produce no proposals.

## Errors (folded)

Acting on a proposal that does not exist (stale UI, retried request) fails
with a clear not-found message and changes nothing — covered inside AC-11's
flow and pinned at the API level during implementation.
