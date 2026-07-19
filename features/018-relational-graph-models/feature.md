---
slug: relational-graph-models
title: Relational graph (GNN) model backend — validated against the paper
outcome: The Models area gains a relational tier — a GNN backend (plus the hybrid GNN-embeddings→GBM combination the paper found best) that learns across linked tables instead of one flat feature table. Its code validity is proven the only honest way public data allows — by reproducing the owner's paper's reference AUROCs on the Berka tasks within tolerance, deterministically: graph model 0.718 (loan_default) / 0.759 (account_churn) / 0.679 (card_adoption), relational-feature baseline 0.765 / 0.902 / 0.800. Trained relational models land in the SAME registry, write predictions as ordinary queryable datasets, and are guided through the same decisions-not-code flow as 012. The torch stack ships as a separate analyst:ml image variant; the default image stays lean.
status: done
autonomy_level: high
owner: igormusic
area: models
tracker_ref: local://relational-graph-models
roadmap_ref: relational-graph-backend
branch: relational-graph-models
size: L
validation_method: "REFERENCE-DATA board: ACs run against the real Berka dataset (downloaded on demand from public mirrors into the test cache, never committed; pinned snapshot + fixed seeds) and assert each tier's holdout AUROC within tolerance of the paper's RESULTS.md (graph 0.7182/0.7592/0.6787, baseline 0.7647/0.9018/0.7999) — the code-validity gate the owner specified, since single feature tables cannot exercise a graph. PLUS the full-e2e stage: the acceptance flow runs against the DEPLOYED analyst:ml CONTAINER (torch-variant image, replay-mode agent, browser-driven) before the feature is done; owner takes over exploratory testing at that gate. Mutation gates on graph-construction integrity, holdout honesty, and seed determinism."
created: 2026-07-19
---

# Feature 018 — Relational graph (GNN) model backend

> PROMOTED 2026-07-19 (owner): full autonomy delegated, same container-gated
> ATDD condition as 012. Owner decisions locked at promotion:
> 1. **Torch & image** — a separate `analyst:ml` image variant (FROM the
>    base image + CPU torch stack) carries torch/torch-geometric/relbench;
>    the container e2e gate runs against `analyst:ml`; the default image
>    stays lean per the 012-plan directive "torch stays out of the image".
> 2. **Reference data** — Berka only. The board validates against the
>    paper's RESULTS.md, each tier against its own reference: graph AUROC
>    loan_default 0.7182 / account_churn 0.7592 / card_adoption 0.6787;
>    baseline (relational features → GBM) 0.7647 / 0.9018 / 0.7999 —
>    ±tolerance, deterministic seeds. Berka downloads from public mirrors
>    (github jlacko/berka-dataset, fallback sorry.vse.cz) — no credentials.
>    Olist is out: Kaggle friction and near-random paper AUROCs (~0.58).
> 3. **Scope** — validated engine + registry integration, including the
>    hybrid GNN-embeddings→GBM path (the paper's best performer). The
>    guided flow reuses 012's UI seams. LLM-guided graph-schema authoring
>    stays a later feature.

Origin: the owner's paper and working pipeline at `~/code/relational-graph`
(relbench + pytorch-frame + torch-geometric, CPU torch 2.8; per-dataset
`hooks.py` for berka/olist; RESULTS.md carries the reference numbers). The
strategic thread and the honest reading of the results are documented in
`../012-guided-predictive-models/research/01-origin-relgraph-findings.md`.

## The contract in one paragraph

012 proved a no-code user can train a trustworthy single-table model. But
analyst's differentiator is its *relational* understanding — validated
PK/FK links, cross-table semantics. This feature makes the model tier match
that: a graph model that learns from the linked structure itself
(accounts→transactions→districts), exposed through the same guided
decisions, the same registry, the same predictions-as-datasets. Because
public relational data is anonymization-damaged (the paper's own finding:
GBM baselines won every task), the feature's honesty bar is NOT "GNN beats
LightGBM" — it is "our implementation reproduces the paper's reference
results deterministically, and the hybrid path is available where structure
carries signal".

## Scope (the cut)

- **In:** Berka reference bundle downloaded on demand + cached (never in
  git); committed graph-construction from workspace FK links (node types =
  tables, edges = validated FKs); committed deterministic GNN trainer
  (heterogeneous GraphSAGE-class model, CPU, seeded) for binary
  classification tasks; hybrid GNN-embeddings→GBM; honest temporal/holdout
  split; AUROC-vs-reference validation; registry integration (same cards,
  metrics in plain language, predictions datasets); `analyst:ml` image
  variant + container e2e board against it; plain "why not available"
  message when torch is absent (default image).
- **Out (later features):** LLM-guided graph-schema authoring as a
  conversation; olist/second reference set; temporal-model UX
  (`relational-temporal-models`); Q&A-predictions integration; GPU.

## Autonomy

`high` — full pipeline delegated in-session (2026-07-19), gated by the
reference-data board and the `analyst:ml` container e2e. Owner takes over
exploratory testing when the board is green.
