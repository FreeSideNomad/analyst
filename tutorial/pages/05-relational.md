---
layout: default
title: Tutorial 5 — models that understand relationships
---

# 5 · Models that understand relationships

[← Train a model without writing code](04-models.html)

The previous chapter's model looked at one table. But your most valuable
signals often live in the *connections* — a loan's risk hides in the
account behind it, that account's transactions, the counterparties those
transactions touch. This chapter is about models that learn from those
connections directly.

This runs on the **ML edition** of the app (the machine-learning stack
is heavy, so it ships as a separate image). Start it:

```bash
docker compose --profile ml up -d
```

Open **http://localhost:8001** → **Models**. On Apple Silicon this
edition runs under emulation — training takes a few minutes instead of
about thirty seconds. That's expected.

## 5.1 Real banking data, one click

In the relational section, click **Add to workspace** on **Berka bank
(relational)**. The nine linked tables you met in chapter 2 arrive
through the normal pipeline — profiled, described, links verified.

## 5.2 Will this loan default?

Pick the question **"Will this loan end in default?"** and start.

Before anything trains, read the framing the app gives you. Two things
deserve your attention:

- *The prediction moment.* The call is made **as of the day each loan
  was granted**, using only what the bank knew by that day. The model is
  graded on later loans it never saw — predicting the past with the
  future is the most common way models lie, and this design rules it
  out.
- *The hidden columns.* The loan's recorded status — how the story
  actually ended — is named and **hidden from the model**, because
  letting it peek would be answering the question with the answer.

Now train. Three models are built on the same honest split:

- a **simple approach**: summary features engineered from the linked
  tables, fed to a standard learner;
- a **graph approach**: a neural network that learns directly from the
  web of connections — accounts, transactions, shared counterparties;
- a **combined approach**: the graph model's learned patterns handed to
  the simple learner — usually the strongest of the three.

The scores are reported side by side, honestly — including when the
simple approach wins (on this public dataset, it sometimes does; real
private data with richer connections is where graphs shine). The
model's story below the scores tells you exactly which tables and links
it learned from, and every trained model reproduces the results of the
published research this pipeline was validated against.

Predictions, as always, land in your catalog as an ordinary dataset —
one row per loan with its actual outcome and predicted risk.

## 5.3 Your database, your question

The finale. The bank data is also sitting in the Postgres you connected
in chapter 2 — the way *your* data would be. Connect it here on the ML
edition (same form: host `berka-db`, port `5432`, database `berka`,
user `postgres`, password `tutorial`), and once it's catalogued, type
into the authoring box:

> Which loans will end in default?

The app drafts the whole task as **decisions laid out for your
approval**: which table is the thing being predicted, the exact
definition of the outcome (a single readable query), the prediction
moment, the time cutoffs (editable), and the columns it will hide from
the model — with the option to hide more yourself. Nothing runs until
you confirm.

When you confirm, the app runs an integrity check on itself before the
real training: it trains a throwaway model on **deliberately scrambled
outcomes**. The score comes back a coin flip — which is exactly right,
because if a model could "predict" scrambled outcomes, something would
be leaking answers into the pipeline. You get to see that check pass
rather than being asked to assume it.

Then train. Same three models, same honest reporting — and the model's
story names *your connection* as the source and states plainly that
training used a temporary local copy that never left your machine.

**What you can do now:** point a relationship-aware model at any
suitably linked data you have — uploaded or connected — describe what
you want predicted in one sentence, and get a model whose every
decision you saw and approved.

---

That's the tour. Everything you touched — the catalog, the receipts
under every answer, the reversible cleanups, the honest model scores —
is the same machinery you'd use on your own data tomorrow. Bring some.

[← Tutorial home](index.html)
