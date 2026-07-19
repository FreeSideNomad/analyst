---
slug: guided-predictive-models
title: Guided predictive models — the Models area (MVP)
outcome: A user who understands concepts but writes no code (no Python, no SQL, no ML functions) trains a trustworthy predictive model on real ingested data through an LLM-guided conversation — task definition, feature selection, honest evaluation — with every mechanical step done by the app, every concept taught at the moment of decision, and every result carrying a trust trail. Predictions land as ordinary queryable datasets. MVP: single-table regression (house prices) on one-click real sample data; the relational/temporal depth, Q&A integration, discovery accelerators, and the relational-graph backend follow as separate features.
status: done
autonomy_level: high
owner: igormusic
area: models
tracker_ref: local://guided-predictive-models
branch: guided-predictive-models
size: L
validation_method: "REALISTIC-DATA board: ACs run against the real Ames dataset (downloaded on demand into the test cache, never committed; fixed snapshot + seeds so metric thresholds are assertable) — the feedback loop iterates until ACs pass on real data. PLUS a full-e2e stage: the acceptance flow runs against the DEPLOYED DOCKER CONTAINER (built image, replay-mode agent, browser-driven) before the feature is done; owner takes over exploratory testing after that gate. Mutation gates on leakage guards and evaluation honesty."
created: 2026-07-14
---

# Feature 012 — Guided predictive models (Models area MVP)

> PROMOTED 2026-07-19 (owner): full autonomy granted, conditioned on the
> acceptance pipeline including a full e2e run against the deployed Docker
> container. Owner directives at promotion: (1) ACs run on realistic
> datasets — downloaded on demand, cached, never in git — creating the
> testing feedback loop that iterates until ACs are met; (2) training uses
> a well-defined deterministic set (snapshot + seed) so quality is
> assertable; (3) the GNN tier (later) validates against the reference
> datasets from the owner's paper (berka/olist) since single feature
> tables cannot exercise a graph model; (4) the charter/PRD scope
> amendment is closed at promotion (see CHARTER.md §4 + docs/PRD.md,
> 2026-07-19). Since parking, features 013–017 shipped — predictions-as-
> datasets now inherit charts, dashboards, exports, and curation for free.

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

## Resume checklist — resolved at promotion (2026-07-19)

- ~~Charter/PRD amendment~~ → closed: CHARTER.md §4 + docs/PRD.md amended,
  owner-approved in-session.
- ~~Gallery as separate feature?~~ → inside the MVP (two OpenML entries is
  a slice, not a feature).
- ~~autonomy_level~~ → high (full autonomy granted, conditioned on the
  container-e2e acceptance stage).
- Models area = a nav peer (Catalog / Query / Charts / Dashboards / Models).
- Deps: scikit-learn + lightgbm in the image; torch stays deferred to the
  graph-backend feature (which will validate against the paper's berka/
  olist reference data).
