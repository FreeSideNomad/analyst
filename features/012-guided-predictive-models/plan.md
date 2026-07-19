---
slug: guided-predictive-models
checkpoint: 4
plan_status: approved  # owner's full-autonomy grant, conditioned on the container-e2e gate
created: 2026-07-19
---

# Plan — 012 guided predictive models (MVP)

## Architecture

**Feasibility is proven, not assumed** (2026-07-19 probes): OpenML 42165 =
1,460 × 81; a plausible 15-feature agent subset trains to linear R² 0.863 /
LightGBM 0.896 (MAE ≈ $17k), byte-deterministic at seed 42. One real
gotcha already caught: pandas-3 string dtype — categorical detection must
use `is_numeric_dtype`, not dtype names.

### Components

1. **Domain — `src/analyst/domain/models.py`** (pure): `PredictionTask
   (task_id, dataset, target, task_type, split{holdout, seed}, features,
   status)`, `ModelRecord(model_id, task, metrics{linear, gbm}, importances,
   version, predictions_dataset)`, `UnknownModelError`, bounded
   `PARAMETER_SCHEMA` (n_estimators, learning_rate, holdout ranges).

2. **Engine — `src/analyst/engine/mltrain.py`** (the ONLY trainer; fixed,
   committed code — the LLM never writes code):
   - `train(frame_source, task, params) -> TrainedResult` — reads the
     feature table via the store, splits deterministically (seed), builds
     the shared preprocessing (numeric passthrough + one-hot categoricals,
     `is_numeric_dtype` detection), fits LinearRegression AND LGBMRegressor,
     computes holdout R²/MAE for both + gbm feature importances, scores
     ALL rows.
   - Structural leakage guards: target excluded from the feature-space by
     construction; split indices disjoint (asserted); guards mutation-gated.
   - Model artifacts pickled under `<data>/models/` (registry sidecar
     `models.json`, 013-pattern).

3. **Sample gallery — `src/analyst/engine/mlsamples.py`**: `fetch_ames()` /
   `fetch_king_county()` via `sklearn.datasets.fetch_openml(data_id=…,
   data_home=ANALYST_ML_CACHE)` (default `/data/ml-cache` in the image,
   `tests/.ml_cache` on the board) → written as CSV → **normal ingestion
   pipeline** (profiled, catalogued like any upload). Cache = second add
   needs no network (AC-1).

4. **Guidance — `src/analyst/agentic/models.py`** (versioned prompt,
   structured output): input = the dataset's planner-style metadata
   (schema + profile facts + catalog text; NEVER rows) + the target.
   Output schema = the blast radius: `{teaching_note, split_note,
   features: [{name, reason}]}` — nothing else it *can* decide. Replay
   cassette `tests/cassettes/models_guidance.json`.

5. **Repository (`StoreRepository`)**: `create_model_task(dataset, target)`
   (guidance → task saved w/ proposed features; failure leaves nothing),
   `update_task_features` (accept/remove; target rejected; empty rejected),
   `train_model(task_id, params?)` (engine → registry entry + predictions
   dataset `<dataset>.predictions.<model_id>` written through the store),
   `models()/model(id)/delete_model`, all persisted via sidecars; offline:
   creating tasks raises the honest error, everything trained keeps
   working. Fixture parity for the workbench browser flow.

6. **API — `routes/models.py`**: gallery (`GET/POST /api/models/gallery`),
   task lifecycle (`POST /api/models/tasks`, `PATCH …/features`,
   `POST …/train`), registry (`GET /api/models`, `GET/DELETE /api/models/{id}`).
   Error mapping as established (400/404/502).

7. **Frontend — `ModelsPage`** (nav peer): gallery cards, the guided
   conversation (teaching notes + AskQuestion-style feature checklist +
   bounded param panel), training progress, model cards (metrics in plain
   English + importances), link to the predictions dataset.

8. **Container e2e — `scripts/container_e2e.sh` + bindings**: build the
   image, run it with `ANALYST_CATALOG_CASSETTE=/cassettes/merged.json`
   (cassette files merged by key — they are flat prompt-hash dicts) and a
   temp volume, wait for health, drive the journey with Playwright, tear
   down. Default ON in the board (`CONTAINER_E2E=0` to skip locally).

### Key decisions
- **The trainer is one committed function** — both models share one
  preprocessing pipeline; metrics comparable by construction.
- **Predictions are written through the normal store** — charts/dashboards/
  exports/Q&A inherit them with zero new plumbing (the 014/015 dividend).
- **Real-data thresholds live in the BOARD, not unit tests** — the
  feedback loop the owner asked for: red until the real Ames run clears
  R² ≥ 0.80 / gbm > linear.
- **GNN tier untouched** — later feature, validated against the paper's
  berka/olist reference data (owner directive), torch stays out of the image.

## Charter Check
| Rule | Status |
|---|---|
| Scope | ✅ amended 2026-07-19 (owner-approved) — predictive modeling in charter §4 + PRD |
| No generated code executed | ✅ guidance output = teaching notes + feature list only; trainer is committed code |
| Governance (no rows to model) | ✅ prompt-spy scenario; engine-local training |
| DuckDB via engine | ✅ feature tables + predictions written through the store |
| AskQuestion on ambiguity | ✅ feature curation is the primitive |
| uv-only, typed | ✅ new deps: scikit-learn, lightgbm, pandas |
| Mutation policy | gates: (1) leakage guard removed → AC-6 red; (2) holdout leak (train on all rows) → AC-5/6 red (metrics inflate); (3) seed ignored → AC-4 red |

**Amendments:** charter/PRD amendment shipped at promotion (7cdf0c8); none further.

## Phasing
1. Gallery + cache (AC-1) and engine trainer w/ unit-first tests on cached
   real data.
2. Guidance module + cassette recording; task lifecycle (AC-2/3/12/14a).
3. Training/eval/predictions/registry/persistence boards green
   (AC-4..10, 14b) — the realistic-data loop.
4. ModelsPage UI + fixtures parity.
5. Container e2e (AC-13) + mutation gates + docs. Owner exploratory
   testing begins.

## Performance budgets
Ames download ~5 MB once (cached); full train (both models) < 10 s CPU;
board adds ~1 min over cache-warm data; container stage ~3–4 min
(image build cached by docker layer cache).

## Test strategy
Per validation_method: the board IS the feedback loop on real data;
15 scenarios (13 in-process, 1 fixtures-browser folded into UI phase, 1
container). Units: trainer determinism/leakage/dtype handling, gallery
cache behavior, parameter bounds, sidecar round-trips, route codes.
Cassette: guidance turns. Three mutation gates as listed.
