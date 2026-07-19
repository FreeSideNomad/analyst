---
slug: guided-graph-authoring
checkpoint: 4
plan_status: approved-in-handoff
created: 2026-07-19
---

# Plan — 019 guided graph authoring

## Architecture

### Components

1. **`engine/relgraph/workspace.py`** (new, committed): the mechanical
   bridge from what analyst knows to what the engine needs.
   - `spec_from_workspace(tables, relationships, *, name, cutoffs)` →
     `DatasetSpec`: profiled types → spec types; validated 009
     `Relationship`s → `ForeignKeySpec`s (never invented — subset by
     construction); date columns → time-column candidates; no sources
     (data is already here), no hooks (owner decision — data arrives
     decoded).
   - `build_from_frames(spec, fetch_frame)` → writes the engine's
     training db from DuckDB-backed frames (uploaded parquet views and
     federated scanner views look identical here). FK integrity check
     unchanged. Cache key includes a content fingerprint so re-authoring
     rebuilds when data changed.
   - `label_columns(label_sql, entity_columns)` → the entity-table
     columns the outcome definition references (duckdb-tokenized
     identifier intersection; over-exclusion is the safe direction) —
     feeds AUTO-exclusion (AC-6).
2. **`engine/relgraph/honesty.py`** (new, committed): `shuffled_label_canary`
   (baseline tier on seed-shuffled labels → AUROC; wiring is honest when
   ≈0.5) and `giveaway_columns` (single-feature quick AUROC > 0.95 →
   flagged) — both cheap (LightGBM-only), run at confirm time.
3. **`agentic/graphauthor.py`**: one bounded authoring turn. Input:
   derived-structure summary + the user's question (text). Output schema:
   `{entity_table, label_sql, time_column, horizon_days, val_cutoff,
   test_cutoff, framing{question,moment,honesty}, reasons{...}}`.
   Guards: label_sql through the existing read-only sql_guard; entity and
   time_column must exist in the derived structure; excluded columns are
   NOT the agent's to decide — computed mechanically via `label_columns`
   and only ever grown by the user. Failure → plain error, nothing
   created (AC-9). Cassette `tests/cassettes/graph_authoring.json`
   (recorded live once by `scripts/record_graph_authoring_cassette.py`,
   byte-for-byte with the bindings).
4. **Repository**: `author_relational_task(source, question)` → derived
   structure + agent proposal + honesty warnings, persisted as a PENDING
   task (`status: proposed`, decisions unconfirmed); `confirm_relational_task`
   → runs canary + giveaway checks, flips to `defined`;
   `train_relational` extended to generated tasks (build_from_frames +
   train_tiers on the generated spec); registry story gains `source`
   (connection name / "uploads") and the local-materialization disclosure
   (AC-11). Re-including a hidden column → refused with reason.
5. **Berka-in-Postgres**: `scripts/seed_berka_postgres.py` loads the
   curated decoded tables into a Postgres via DuckDB's postgres ATTACH
   (no new deps). The board self-provisions a `postgres:16-alpine`
   container (fixed name, atexit cleanup — the 018 container pattern), so
   CI needs no external DB; locally the same script can seed the demo
   compose Postgres for exploratory testing.
6. **UI (ModelsPage)**: the relational section gains "on your data" —
   pick a source (connection or uploaded tables), type the question,
   review the decision card (structure, outcome, moment, cutoffs, hidden
   columns, warnings), confirm & train. Registry card shows the source.
7. **Container gate**: analyst:e2e-ml + seeded postgres container on one
   docker network; the journey connects the DB through the UI, authors,
   confirms, trains, verifies predictions + story (AC-12).

### Key decisions

- **The curated 018 bundle is the generator's ground truth** (AC-4/5):
  same data, three arrival paths (curated, uploads, connected DB) must
  converge to the same numbers. No new reference data.
- **Excluded columns are never the LLM's call** — mechanical from the
  label SQL, user can only add. This makes the leakage judgment
  deterministic and mutation-gateable.
- **Charter disclosure**: training materializes a transient local build
  of connected tables (federation queries stay in-place; training cannot)
  — stated in the registry story and docs.

## Charter check

| Rule | Status |
|---|---|
| Bulk data never reaches the LLM | ✅ authoring turn carries structure summary only; asserted by AC-10 |
| Local execution, connected DBs read-only in place | ✅ reads via scanners; ⚠→✅ training's local materialization DISCLOSED (feature.md decision 4, AC-11) |
| Determinism | ✅ same seeds; canary shuffle seeded |
| Autonomy / verification / mutation | high; equivalence + structural gates; 3 gates below |

## Phasing

- **P1** — workspace.py + upload-path equivalence in units (mechanical
  generation, no agent): generated spec from ingested Berka files
  reproduces the curated reference.
- **P2** — postgres seed + connected-path equivalence (self-provisioned
  postgres container in tests).
- **P3** — honesty.py + graphauthor + cassette + repository/routes
  (author→confirm→train), failure atomicity.
- **P4** — UI + board bindings (12 in-process green).
- **P5** — container gate, mutation gates, docs, sweep, PR, CI, merge.

## Mutation gates

1. **Invented edge**: spec_from_workspace emits an FK not in the
   validated set → structure scenario red (subset assertion).
2. **Exclusion completeness**: label_columns returns empty → hidden-columns
   + canary scenarios red.
3. **Canary honesty**: shuffle disabled (canary trains on real labels) →
   coin-flip scenario red.

## Test strategy

Per validation_method: equivalence board on both arrival paths vs the 018
reference; structural gates; self-provisioned postgres in tests; the
deployed analyst:ml + demo-DB container journey; units for workspace
mapping, label-column extraction, canary, giveaway detection; existing 18
boards stay green (full sweep).
