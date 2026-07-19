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

## Governance, as always

The model only ever guides: it sees schema, profile facts, and catalog text —
never your rows. Offline, existing models and their predictions keep working;
starting a new one explains plainly that guidance needs the AI connection.

[Administration →](admin.html)
