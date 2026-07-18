---
slug: cross-database-joins
checkpoint: 4
plan_status: approved  # standing session delegation
created: 2026-07-18
---

# Plan — 017 cross-database joins

## Architecture

**Probe-first plan.** The 2026-07-18 engine probe showed the layers below
the NL surface already work: two scanner connections ATTACH into the store,
a two-connection join validates and executes locally, and discovery with
`include_federated` finds the cross-DB key. The feature is therefore an
ENABLEMENT + PIN, not a build:

1. **No new execution machinery.** The 007 local scanner path carries the
   join; 008's single-DB pushdown is untouched (different path).
2. **Planner surface**: `qa._tables` already offers all attached queryable
   tables and `qa._relationships` already carries catalog relationships —
   the board proves the planner (live-recorded) writes the two-connection
   join from that view.
3. **Synthetic sample kit** `scripts/make_cross_dbs.py`: crm.db + billing.db,
   deterministic, documented totals (enterprise 150 / smb 50). Synthetic on
   purpose — join mechanics need controlled keys, not organic signal.
4. **Board seam**: two SQLite connections through the real DatabaseManager;
   planner cassette with four live-recorded turns (join, single-DB count,
   detached abstention, post-credential-restore join).

## Charter Check
| Rule | Status |
|---|---|
| Governance (bulk local; metadata+capped results only) | ✅ pinned by the exchange-spy scenario |
| DuckDB via engine layer | ✅ no new SQL outside engine |
| Prompts versioned/cassette-recordable | ✅ planner unchanged; cassette added |
| API thin / domain pure | ✅ no API or domain changes |
| Mutation policy | gates: federated discovery off → AC-3 red; DB tables invisible to planner → AC-1 red; idempotent-attach fix reverted → AC-5 red |

**Amendments:** none.

## Phasing
1. Kit + bindings + cassette; 2. defect fixes the board surfaces; 3. gates + docs.

## Test strategy
Per validation_method: 8-scenario board (all in-process; no UI surface
changed), 4-turn live cassette, the idempotent-attach unit pin, three
mutation gates. Existing boards = the AC-7 regression guard.
