---
slug: guided-predictive-models
title: Guided predictive models — the Models area (MVP)
outcome: A user who understands concepts but writes no code (no Python, no SQL, no ML functions) trains a trustworthy predictive model on real ingested data through an LLM-guided conversation — task definition, feature selection, honest evaluation — with every mechanical step done by the app, every concept taught at the moment of decision, and every result carrying a trust trail. Predictions land as ordinary queryable datasets. MVP: single-table regression (house prices) on one-click real sample data; the relational/temporal depth, Q&A integration, discovery accelerators, and the relational-graph backend follow as separate features.
status: parked
autonomy_level: null
owner: igormusic
area: models
tracker_ref: local://guided-predictive-models
branch: guided-predictive-models
size: L
created: 2026-07-14
---

# Feature 012 — Guided predictive models (Models area MVP)

> Parked 2026-07-14: approved in shape, deliberately sequenced **after** the
> existing planned features (data normalization detection, cross-dataset
> joins, dashboards, charts/exports — some of which this feature builds on).
> Resume with `/engineer.discuss guided-predictive-models`.

Origin: the user's relational-graph research (`~/code/relational-graph` —
paper + working `relgraph` pipeline on real data). The full discussion is
documented in `research/`:

| File | Thread |
|---|---|
| [research/01-origin-relgraph-findings.md](research/01-origin-relgraph-findings.md) | What the research actually showed, and what that implies for build order |
| [research/02-persona-and-teaching-ux.md](research/02-persona-and-teaching-ux.md) | Who this is for; teaching-as-decisions UX; plain-language metrics |
| [research/03-sample-datasets.md](research/03-sample-datasets.md) | Verified sample-dataset research — accepted, rejected, and why |
| [research/04-capability-map-and-mvp.md](research/04-capability-map-and-mvp.md) | The A–K capability map, the MVP cut, the follow-on ladder |
| [research/05-architecture-direction.md](research/05-architecture-direction.md) | Declarative artifacts, not generated scripts; governance; dependencies |

## The contract in one paragraph

analyst already turns raw data into a profiled, catalogued, relationship-
validated workspace. This feature adds the next question a data owner
actually asks: *"what will happen?"* — churn, default, price — answered the
same way feature 003 answers *"what happened?"*: conversationally,
locally-executed, confidence-gated, and fully inspectable. The differentiator
is not AutoML horsepower; it is that the semantic catalog lets the agent
reason about features in domain language, and that validated relationships
turn thin-but-recent real data into rich training tables.

## MVP scope (the cut)

- **In:** sample gallery (Ames + King County via OpenML, no credentials);
  guided task definition (regression only); guided single-table feature
  selection; local training (linear regression + LightGBM); honest holdout
  evaluation in plain language; minimal model registry; predictions written
  back as a queryable dataset with lineage.
- **Out (each a follow-on feature):** multi-table/relational features,
  temporal splits & horizons, classification tasks, Q&A routing and
  questions-over-predictions, per-row explanations, Kaggle-gated samples,
  automated feature/algo discovery, the GNN backend, drift monitoring.

## Hard invariants carried forward

- **Governance:** training and scoring run locally (DuckDB → engine). Only
  schema, profiles, capped samples, and small results reach the LLM — the
  standing invariant is untouched by this feature.
- **No generated code is ever executed.** The LLM emits declarative,
  validated artifacts (task spec, SQL, bounded parameters); training is
  fixed, committed, unit-tested engine code. See research/05.

## To resolve on resume (discover-acs inputs)

- Charter/PRD scope amendment (predictive modeling is a scope extension —
  charter changes are PR'd and human-approved). Draft wording before ACs.
- Is the sample gallery its own smaller feature shipped first? It has value
  independent of Models (demo data for every existing feature).
- autonomy_level (parked features carry none).
- Where the Models area lives in the frontend shell (nav peer of
  Catalog/Query, or inside the workbench).
- New Python deps: scikit-learn + lightgbm in the single image (small,
  acceptable); torch explicitly deferred to the graph-backend feature.
