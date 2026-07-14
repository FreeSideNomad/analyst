# 01 — Origin: the relational-graph research and what it actually showed

> Source: `~/code/relational-graph` — the paper *Relational Graphs in
> Commercial Banking* plus `relgraph`, a working two-layer pipeline run on
> real data (results of 2026-07-11). Based on relational deep learning
> (Leskovec/Stanford/Kumo.ai; RDL paper arXiv:2312.04615; RelBench).

## What relgraph is

A generic engine (`src/relgraph/`) that takes any relational dataset
described purely by metadata — `schema.yaml` (sources, tables, keys, time
columns, split timestamps) and `tasks/*.yaml` (entity + label SQL + horizon)
— and:

1. builds a DuckDB database,
2. materializes prediction tasks from label queries,
3. trains **two models per task on identical out-of-time splits**:
   - **graph** — relational deep learning: tables → node types, FKs → edges,
     torch-frame column encoding, heterogeneous GraphSAGE with temporal
     neighbor sampling (each prediction sees only rows dated before its
     as-of time). No feature engineering.
   - **baseline** — the traditional approach *automated*: schema-traversal
     window aggregates (count/sum/mean/recency over 30–365-day windows along
     FK paths) fed to LightGBM. ~300 lines of generic, task-agnostic code.
4. publishes the comparison (`RESULTS.md`, regenerated from run artifacts).

## The results (test AUROC, 2026-07-11)

| Task | Baseline | Graph |
|---|---|---|
| berka / loan_default | 0.765 | 0.718 |
| berka / account_churn | 0.902 | 0.759 |
| berka / card_adoption | 0.800 | 0.679 |
| olist / late_delivery | 0.583 | 0.518 |
| olist / low_review | 0.577 | 0.514 |
| olist / repeat_purchase | 0.625 | 0.480 |

## The honest reading (the paper's own, sharpened in discussion)

1. **The automated baseline won every task.** Gradient boosting on
   schema-derived window aggregates is a strong opponent at these dataset
   sizes, and the pure-GNN "replaces feature engineering" pitch understates
   how cheaply feature engineering can be *automated*.
2. **But "GNN lost" is the wrong conclusion — "GNN was untestable" is
   right.** Berka's anonymization destroyed the cross-account structure the
   graph thesis depends on: only 31 genuinely shared counterparties survived
   out of ~8,000. The paper's contagion argument cannot be tested on public
   banking data. Where structure carried real signal, adding it helped
   substantially: deriving a counterparty node type from transfer records
   lifted loan default from 0.635 → 0.718 with four-hop sampling — most of
   the way to the baseline, from nothing but the schema and a label query.
3. **Winning tabular models come from domain features someone thinks of.**
   The olist baseline's edge came largely from ONE engineered ratio (the
   promised delivery window) that no generic traversal invents and the GNN
   has no easy way to represent. Generic window aggregates are a floor, not
   a ceiling; human (or LLM-guided) judgment supplies the ceiling.
4. Hybrids (GNN embeddings → gradient boosting) report the best results in
   recent literature; deliberately out of relgraph's scope, and out of
   analyst's near-term scope too.

## What this implies for analyst

- **Build order: guided features + LightGBM first, graph later.** The v1
  value is the guided workflow; the baseline algorithm is proven, cheap
  (small deps), and CPU-friendly. The GNN earns a slot only where data size
  and FK integrity justify it — a *gate to check*, not a default.
- **The declarative task format is proven.** relgraph's `tasks/*.yaml`
  (entity + label SQL + horizon) is exactly the artifact analyst's guided
  conversation should produce. See research/05.
- **analyst already manufactures relgraph's inputs.** `schema.yaml` is
  analyst's profiles + discovered-and-validated FK relationships; the
  metadata description of meaning is the semantic catalog. What relgraph
  required a human to author, analyst derives automatically — that is the
  integration thesis of this feature.
- **The relgraph automated baseline itself (FK-path window aggregates) is
  the seed of the "discovery accelerators" follow-on** — generalized, it
  becomes analyst's automated feature-proposal engine for relational data.
