---
layout: default
title: Tutorial 5 — relational models on your data
---

# 5 · Relational models on your data

*(features 018 relational graph models, 019 guided graph authoring —
the ML image variant)*

[← Guided models](04-models.html)

The finale: models that learn from the **links between tables** — a
graph neural network validated against published research — and then the
real trick: pointing it at a database *you* connect, with the task
authored from a plain-English question.

The torch stack is heavy, so it ships as a separate image. From
`tutorial/`:

```bash
make app-ml    # builds the ML variant, starts it on :8001 (+ Berka Postgres)
make berka-db  # seeds the Postgres with the real PKDD'99 Berka banking data
```

Open **http://localhost:8001** → **Models**. *(On Apple Silicon the ML
image runs emulated — training takes a few minutes instead of ~30
seconds. That's expected.)*

## 5.1 The curated bundle — research, reproduced

1. In **Relational — learn across linked tables**, click
   **Add to workspace** on **Berka bank (relational)**.
2. **Expected:** nine real linked tables (accounts, loans, one million
   transactions…) arrive through the normal pipeline, links validated.
3. Pick the question **"Will this loan end in default?"**
   (**Relational task**) and **Start**. Read the **Task framing** and the
   **Excluded outcomes** — the columns that record how each loan ended,
   named and hidden, *because predicting with them would be answering
   the question with the answer*.
4. **Train relational model**. **Expected:** three models on one honest
   time split — the **simple approach** (engineered features), the
   **graph approach** (a GNN passing messages along the validated
   links), and the **combined approach** (usually strongest). The
   **Relational story** tells you exactly what the graph learned from;
   the scores match the published reference results for this dataset.
   Note the honesty: when the simple approach reads the risk best, the
   evaluation *says so*.

## 5.2 YOUR database, your question — the app authors the task

5. Still on :8001, use **Connect a database**: engine `postgres`, host
   `berka-db`, port `5432`, database `berka`, user `postgres`, password
   `tutorial` — the database `make berka-db` seeded. **Expected:** nine
   tables catalogued in place, links validated cross-source.
6. In the relational section, type into **Authoring question**:
   *"Which loans will end in default?"* → **Author from question**.
7. **Expected — the decisions card:** the entity being predicted, the
   exact outcome definition (a single read-only SELECT you can read),
   the prediction moment, honest time cutoffs (editable), and the
   **Hidden outcome columns** — derived automatically from the outcome
   definition plus the agent's judgment about post-outcome columns. Try
   the **Hide another column** box: the hidden set can only ever grow.
8. **Confirm decisions**. **Expected — the honesty checks:** the app
   just trained a throwaway model on *deliberately shuffled outcomes*
   and reports the score — a coin flip (~0.50), which is exactly what an
   honest pipeline must produce; anything more would mean a leak in the
   plumbing. Columns that alone give the answer away would be flagged
   here.
9. **Train locally**. **Expected:** the same three-tier result as the
   curated bundle — same data, different arrival path, same truth — and
   the **Relational story** now names *your connection* as the source
   and states plainly that training used a **temporary local copy that
   never left the machine**.

## 5.3 What you just verified

The whole promise, end to end: real data in, meaning and links proven
against the data, every answer carrying receipts, models trained locally
through confirmable decisions, honesty demonstrated structurally — and
none of it required writing a line of code.

[← Tutorial home](index.html)
