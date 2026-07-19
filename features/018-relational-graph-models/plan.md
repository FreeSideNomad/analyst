---
slug: relational-graph-models
checkpoint: 4
plan_status: approved-in-handoff
created: 2026-07-19
---

# Plan — 018 relational graph (GNN) models

## Architecture

The owner's paper repo (`~/code/relational-graph`, same author) is the
reference implementation; the engine is **vendored and adapted, not
reinvented** — reproducing its numbers is the code-validity gate, so the
port stays faithful (same architecture, hyperparameters, split policy,
seeding, single-thread determinism for small tasks).

### Components

1. **`src/analyst/engine/relgraph/`** — the adapted engine (committed,
   fixed code; the LLM never writes training code):
   - `schema.py`, `loader.py`, `builddb.py`, `tasks.py`, `features.py`,
     `models/baseline.py`, `models/graph.py`, `train.py` — from the paper,
     with: cache rooted at `ANALYST_ML_CACHE/relgraph/`; berka's
     `schema.yaml`/task YAMLs/`hooks.py` carried as package data; errors
     mapped to analyst conventions; no CLI.
   - Extensions the paper lacks: per-entity **prediction output** (test +
     all splits, probabilities); **embedding extraction** (final GNN layer
     per entity) feeding the **hybrid tier** (embeddings + baseline
     features → LightGBM, same split).
2. **Torch optionality** — `pyproject` optional extra `ml` (torch,
   torch-geometric, relbench, pytorch-frame, pyyaml). `mlgraph.available()`
   probes importlib; absent → the relational tier answers with the honest
   "needs the ML variant" message (AC-10). Lean image never installs the
   extra.
3. **Berka gallery bundle** — the model gallery gains a relational entry:
   download via loader (public mirrors, cached), decode via hooks, then
   ingest each table's CSV through the NORMAL ingestion pipeline (AC-1);
   relationships validated by the existing feature-009 PK/FK machinery.
   Training reads the engine's own DuckDB build (faithful to the paper);
   the workspace tables are the user-facing catalog surface.
4. **Repository + routes** — relational task lifecycle mirroring 012:
   `relational_tasks` (framing from task YAML: plain-language question,
   as-of framing, named excluded outcome columns — AC-2), suitability
   check (validated links + time column, AC-11), `train` running
   graph + baseline + hybrid tiers, registry entries in `models.json`
   (kind: relational), predictions ingested with cataloguer bypass
   (012 pattern), failure atomicity (AC-12).
5. **UI** — ModelsPage grows a relational section reusing 012 seams:
   bundle card, task card (framing + excluded columns), train button,
   registry card with the relational story (tables/links, time split,
   seed, split sizes, tier scores — AC-8).
6. **`analyst:ml` image** — Dockerfile stage `ml` (`FROM runtime`,
   `uv sync --extra ml`); default target unchanged (AC-10 lean-size
   guard). Board's container gate builds/runs the `ml` target.
7. **Board bindings `acceptance/e2e_018.py`** — in-process scenarios via
   StoreRepository seam on real Berka (cache under tests/.ml_cache);
   agent turns (if any teaching text is agent-worded, else static
   framing from task YAML — DECISION: framing is deterministic from task
   metadata, NO agent turn needed for MVP; AC-13 then asserts the
   task-definition path sends nothing anywhere: zero exchanges). Container
   scenario per 012 pattern against analyst:ml.

### Key decisions

- **Framing without the agent**: task framing (AC-2) is authored, static,
  per-task metadata (extending the task YAML with a `framing:` block) —
  deterministic, offline-safe, and honest (the paper's task docs already
  contain the language). The agent adds nothing for three fixed reference
  tasks; LLM-guided authoring is the deferred later feature. AC-13's
  governance assertion becomes: the whole journey performs zero agent
  exchanges (stronger than "no rows").
- **Determinism**: Berka tasks are all `<LARGE_TASK_ROWS` → single-thread
  torch path → same-seed bitwise reproducibility (paper's contract).
- **Version risk**: paper pinned torch 2.8/py3.12; analyst is py3.14 →
  torch 2.13 (cp314 wheels exist; whole stack supports 3.14). AUROC drift
  across torch versions is the main reproduction risk; the ±0.03
  tolerance + feedback loop absorbs or surfaces it. If a number lands
  outside tolerance, that is a finding to bring back — not silently
  retuned.

## Charter check

| Rule | Status |
|---|---|
| Raw bulk data never reaches the LLM | ✅ stronger here: zero agent exchanges in the journey |
| Local execution (DuckDB, no copies of connected DBs) | ✅ training local; berka is downloaded sample data, not a connected DB |
| Determinism / reproducibility | ✅ seeded, single-thread, reference-validated |
| Autonomy stance | high, owner-delegated 2026-07-19; container gate = handover point |
| Verification independence | board asserts paper numbers the implementation cannot see |
| Mutation policy | 3 gates (below) |
| Performance budgets | fast board ≈ loan_default only; ML_FULL matrix pre-ship + nightly |

No deviations; no amendment needed (predictive-model scope was amended
into CHARTER/PRD 2026-07-19 with 012).

## Phasing

- **P1 — engine port + reference loop**: vendored engine trains
  loan_default graph+baseline from a fresh on-demand download; unit
  asserts ±0.03 vs RESULTS.md; determinism unit. THE code-validity core.
- **P2 — hybrid + predictions**: embeddings → LightGBM; per-entity
  predictions; hybrid guard (≥ stronger parent − 0.05).
- **P3 — product surface**: gallery bundle via normal ingestion + FK
  validation; repository/routes/UI; in-process board bindings green
  (13/15).
- **P4 — ship gate**: analyst:ml image + container binding (15/15);
  ML_FULL matrix once locally; mutation gates; docs; full sweep; PR; CI;
  merge; rebuild owner's containers.

## Mutation gates (commit first, mutate, expect red, revert)

1. **Graph integrity**: excluded outcome columns NOT dropped
   (`loan.status` reaches the graph) → reference scenarios red (scores
   inflate past tolerance ceiling).
2. **Holdout honesty**: temporal split ignored (train on all rows /
   future-visible sampling) → reference + comparison scenarios red.
3. **Seed determinism**: seed not applied to loaders/model → determinism
   scenario red.

## Test strategy

Per `validation_method`: reference-data board (real Berka, on-demand,
never in git, pinned mirrors, fixed seeds, per-tier ±0.03) + ML_FULL
matrix (account_churn, card_adoption) run at least once pre-ship and
nightly-gated; container e2e against the built analyst:ml image; unit
suite for the engine (fast paths use --smoke mode where thresholds are
not asserted); mutation gates above; existing 001–017 boards must stay
green (full sweep before PR).
