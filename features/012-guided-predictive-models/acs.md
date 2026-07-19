---
ac_count: 14
high_priority_count: 9
discovered: 2026-07-19
mode: greenfield
note: >
  Full autonomy (owner grant 2026-07-19) conditioned on AC-13. Realistic-data
  directive: quality ACs assert thresholds on the REAL Ames dataset with a
  pinned snapshot + fixed seeds — the feedback loop iterates until they pass.
---

# Acceptance criteria — 012 guided predictive models (MVP)

## AC-1: The gallery delivers real data on demand (High)
The Models area offers the Ames and King County house-price datasets;
picking one downloads it on demand (cached locally, never stored in git),
and it arrives through the NORMAL ingestion pipeline — profiled,
catalogued, queryable like any upload.

## AC-2: A model is defined through a guided conversation (High)
"New model" leads a conversation that produces a saved prediction task —
what to predict (SalePrice), task type (regression, explained via the
line-fitting anchor), and an honest holdout split (explained as a decision:
"I'll hide 20% and grade myself — fair?"). The task is a declarative
artifact; no generated code is ever executed.

## AC-3: Features are proposed in domain language and user-curated (High)
The agent proposes a feature subset with plain-language reasons drawn from
the catalog; the user accepts or removes features through the AskQuestion
primitive; the chosen features materialize as a feature table — itself a
queryable dataset with lineage.

## AC-4: Training runs locally and deterministically (High)
Linear regression (the anchor) and LightGBM (the upgrade) train locally on
the deterministic split (pinned snapshot + fixed seed); the same inputs
always produce the same model and metrics.

## AC-5: Evaluation is honest and meets REAL thresholds (High)
On the real Ames data, the holdout evaluation reports plain-English quality
("typically off by $X on a house") with full stats one expand away — and
the pinned thresholds hold: LightGBM holdout R² ≥ 0.80 and LightGBM beats
the linear baseline. These run against the real dataset; the loop iterates
until they are green.

## AC-6: Leakage is structurally impossible (High)
The target column can never be selected as a feature, and holdout rows
never influence training — both guarded in code and mutation-gated.

## AC-7: Predictions land as an ordinary dataset (High)
Scoring writes a predictions dataset (row id, actual where known,
predicted, model version) that querying, charts, dashboards, and exports
consume like any other data.

## AC-8: The model registry tells the model's story (Medium)
Each model lists its data (with fingerprint), chosen features, split,
seed, metrics, and version history; retrain and delete work; global
feature importances are shown in plain language.

## AC-9: Models and predictions survive a restart (High)
After a restart, the registry, trained models, and prediction datasets are
intact; scoring new rows needs no retraining.

## AC-10: Parameters are bounded and optional (Medium)
The agent picks defaults from a bounded parameter schema; a simple panel
exposes the same knobs; nothing requires touching them.

## AC-11: Offline degrades honestly (Medium)
Defining a model needs the AI features and says so plainly when absent;
already-trained models keep scoring and their registry keeps working
fully offline.

## AC-12: Governance holds (High)
Only schema, profile facts, catalog text, and the user's decisions cross
to the LLM — never training rows; training and scoring are local engine
code; the exchange is cassette-recordable and pinned by a prompt spy.

## AC-13: The full flow passes against the deployed container (High)
The end-to-end journey — gallery → task definition → features → training →
evaluation → predictions dataset — runs green against the BUILT DOCKER
IMAGE (replay-mode agent, browser-driven) as part of the acceptance
pipeline. This is the owner's condition for autonomy; exploratory testing
hands over after this gate.

## AC-14: Errors are clean (folded) (Medium)
Unknown model/task ids fail as not-found; a failed agent turn leaves no
half-created task; a failed dataset download reports plainly and retries
cleanly; empty feature selections are rejected with a message.
