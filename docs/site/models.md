---
layout: default
title: Guided models
---

# Guided predictive models

[← Manual home](index.html)

Switch to **Models** to train a real prediction model without writing a line
of code. The whole flow is a guided conversation of decisions — which data,
what to predict, which columns to use — while all the actual machine learning
runs locally in fixed, audited code.

## Start with real data

The **sample gallery** offers well-known real datasets (Ames house prices,
King County house sales). One click downloads the data on demand, caches it
locally, and pushes it through the normal ingestion pipeline — profiled and
catalogued like any upload. Adding the same sample again is instant and
offline: it comes from the cache. Any of your own ingested datasets works
too.

## Define the task as decisions

Pick a dataset and the column to predict, and press **Start model**. The
agent responds with:

- a **teaching note** — two friendly sentences explaining what predicting
  this target means for this data, anchored to basic linear regression;
- a **split note** — why a fifth of the rows is held out as an honesty test,
  phrased as a decision you're making;
- a **feature proposal** — 10–18 columns, each with a plain-language reason
  tied to what that column means in the catalog.

You curate the proposal: untick anything you disagree with, then accept.
The accepted features materialize as a queryable feature table.

Guardrails are structural, not advisory: the target itself can never be a
feature (that would be answering the question with the answer), and the
held-out rows never touch training.

## Deterministic local training

Training runs entirely on your box, in committed code the LLM never writes.
Two models train on the same preprocessing: a **linear regression** (the
teaching anchor) and **LightGBM** (the upgrade), so their scores are
comparable by construction. Same data + same seed ⇒ identical metrics, every
time. Parameters are optional and bounded — sensible defaults work, and
out-of-range values are rejected with the allowed range.

## Honest evaluation

Scores come only from the held-out rows the models never saw. The registry
card shows both models' fit (R²) and typical error (MAE) — including a
plain-dollars sentence like *"Typically off by $16,000 on homes the model
never saw"* — plus the most influential features in plain language.

## Predictions are ordinary data

Every trained model writes its predictions back as a **normal dataset** —
one row per record with the actual value, the predicted value, and whether
that row was held out. Query it, chart it, join it like anything else.
Models and predictions persist across restarts.

## Relational models — learning across linked tables (ML variant)

Where 012-style models learn from one flat table, the **relational tier**
learns from the *links themselves*: pick the Berka banking bundle from the
gallery (nine real linked tables — accounts, loans, a million
transactions — downloaded on demand from public mirrors) and choose a
question like *"Will this loan end in default?"*. Three models train
locally on the same honest time split:

- the **simple approach** — engineered features from the linked tables
  into gradient boosting;
- the **graph approach** — a graph neural network that passes messages
  along the validated table links;
- the **combined approach** — the graph model's learned representations
  fed to the boosting model (usually the strongest).

The framing is decisions, not code: the prediction moment is explained,
and the columns that record the outcome are *named and hidden* — because
predicting with them would be answering the question with the answer.
Scores are AUROC (0.5 = coin flip, 1.0 = perfect ranking), reported for
all three tiers truthfully — when the simple approach wins, the registry
says so. The implementation is validated by reproducing the reference
results of published research on this exact dataset, deterministically.

The torch stack is heavy, so it ships as a separate image target — build
with `docker build --target ml` (linux/amd64). The default image stays
lean; in it, the relational tier explains plainly that the ML variant is
needed while everything else keeps working.

## Author a relational model on YOUR data

The relational tier is not just for the sample bundle: type a question
about your own linked tables — uploaded files or a **connected
database** — and the app authors the task with you. The graph structure
is derived from what the workspace has already validated (profiled
types, integrity-checked links, date columns); the agent proposes the
decisions — which table is the entity, the exact outcome definition, the
prediction moment, the honest time cutoffs, and the columns that must be
hidden because they record the outcome — and **you confirm or adjust
every one** before anything trains.

Honesty stays provable even where no reference results exist: at
confirmation the app trains a quick model on deliberately shuffled
outcomes (an honest pipeline scores a coin flip — anything more means a
leak in the plumbing), flags any column that alone nearly perfectly
predicts the outcome, and the registry story names the data's source and
states that training used a temporary local copy that never left the
machine.

## Governance, as always

The model only ever guides: it sees schema, profile facts, and catalog text —
never your rows. Offline, existing models and their predictions keep working;
starting a new one explains plainly that guidance needs the AI connection.

[Administration →](admin.html)
