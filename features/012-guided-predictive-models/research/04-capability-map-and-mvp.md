# 04 — The capability map and the MVP cut

## Three layers, not three alternatives

The discussion reframed the original "LightGBM vs GNN" tension into layers
that share one spine (the declarative task definition, research/05):

1. **Guided ML (v1)** — LLM leads task definition, feature building,
   training, honest evaluation. Light deps, all local, trust trail
   throughout.
2. **Discovery accelerators (v2)** — automated feature discovery
   (featuretools-style DFS / the relgraph FK-path window aggregates,
   generalized) and model/algo selection (FLAML/AutoGluon-class) as
   accelerants *inside* the same flow. Research spike before commitment.
3. **Relational graph backend (v3)** — the GNN as a second model type behind
   the same task definition, activated only where data size and FK integrity
   justify it (the gate relgraph's findings demand). torch is heavy → likely
   an optional image variant. Validated against RelBench baselines.

## The complete capability map

| # | Capability | What it is |
|---|---|---|
| A | **Sample gallery** | One-click real datasets (research/03), license/T&C gate, download-on-demand through normal ingestion. Kaggle token via the 011 vault. |
| B | **Guided task definition** | Conversation → a saved prediction task: entity, target, task type (regression / yes-no), honest split (out-of-time when timestamps exist; random otherwise). Concepts taught as decisions (research/02). |
| C | **Guided feature building** | Agent proposes features in domain language from the catalog; user approves/adjusts via AskQuestion; materialized as a denormalized feature table — itself a queryable dataset with lineage. Joins only along validated relationships. |
| D | **Train + honest evaluation** | Local training: linear regression as the anchor, LightGBM as "the upgrade". Agent-chosen defaults; simple parameter UI over the same bounded schema. Plain-English metrics; full stats one expand away. |
| E | **Model registry** | Per-workspace models: data, features, split dates, metrics, versions, retrain, delete — the model's trust trail. |
| F | **Predictions as datasets** | Scoring writes an ordinary dataset (entity, score, model version). Tables, exports, and Q&A work on predictions for free. |
| G | **Q&A integration** | "Which houses are undervalued?" routes into the model flow; questions span facts × predictions ("average predicted vs actual price by neighborhood"). Models become catalog citizens. |
| H | **Explainability** | Global feature importance; per-row "this scored high because X, Y" — plain language over SHAP-style attribution. |
| I | **Discovery accelerators** | Layer 2 above. Spike first. |
| J | **Relational graph backend** | Layer 3 above. |
| K | **Monitoring / drift** | Score drift, retrain nudges. Explicitly *later*. |

## The MVP cut: A(small) + B + C(single-table) + D + E(minimal) + F

**Walkthrough (the acceptance narrative):** open Models → pick **Ames** from
the gallery (two entries only: Ames + King County; OpenML mechanism, no
credentials) → it ingests/profiles/catalogues like any upload → "New model":
*"What should I predict?"* → SalePrice → "a dollar amount, so this is
regression — like the line-fitting you know, but able to bend" → agent
proposes ~15 of the 80 features with reasons; accept/toss via AskQuestion →
*"I'll hide a random 20% of houses and grade myself on them — fair?"* →
trains linear + LightGBM locally in seconds → *"Typical miss: $31k linear,
$19k LightGBM — here's why the upgrade helped"* → predictions land as a
dataset, immediately queryable and exportable → registry shows the model;
trust trail shows everything (features, split, params, metrics, SQL).

**Why Ames first is load-bearing:** single-table and timeless, so the MVP
needs neither join machinery nor as-of-time discipline — the two hardest
parts — while still exercising the entire guided loop on real data with
rich features.

**Deliberately out of the MVP** (each is a follow-on): multi-table features,
temporal splits/horizons, classification, Q&A routing, per-row explanations,
Kaggle-gated samples, I/J/K entirely.

**What the MVP validates — the two real bets:**
1. A guided conversation can carry someone from "basic linear regression" to
   a trustworthy trained model with zero code.
2. Predictions-as-datasets is the right integration spine.

**New dependencies:** scikit-learn + LightGBM (small, CPU, image-friendly);
OpenML download is plain HTTPS. torch explicitly deferred.

## The follow-on ladder (each its own DAE feature; roadmap items)

1. **Relational features + temporal splits + classification** — Home Credit
   becomes runnable; this is where the relgraph paper's substance lands.
2. **Q&A × predictions** (capability G).
3. **Discovery accelerators** (capability I) — research spike first.
4. **Relational graph backend** (capability J) — RelBench-validated,
   optional image.
5. **Full sample gallery** — NYC+PLUTO, UK PPD+EPC (join-powered samples).

## Sequencing decision (why parked)

Product owner: finish the existing planned features first (data
normalization detection, cross-dataset joins, dashboards, charts/exports).
Two of those are natural prerequisites here anyway: cross-dataset joins
(feeds C's relational successor) and charts/exports (model outputs want
them). Parked, not dropped — resume via `/engineer.discuss
guided-predictive-models`.
