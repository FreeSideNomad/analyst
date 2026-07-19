---
layout: default
title: Tutorial 4 — guided models
---

# 4 · Guided models

*(feature 012 — guided predictive models; needs the AI key for the
guidance step)*

[← Databases](03-databases.html)

You'll train a real house-price model on real data — 1,460 actual home
sales — without writing a line of code. Every mechanical step is the
app's job; every *decision* is yours.

## 4.1 Real data, one click

1. Switch to **Models**. In the sample gallery, click
   **Add to workspace** on **Ames house prices**.
2. **Expected:** the dataset downloads (once — it's cached after),
   flows through the normal ingestion pipeline, and appears in the
   catalog: 1,460 homes, 81 columns, profiled and catalogued.

## 4.2 Decisions, not code

3. Under **New model**, pick dataset `ames.csv` (**Model dataset**) and
   `SalePrice` (**Model target**), then **Start**.
4. **Expected:** a **Teaching note** (what predicting this target means,
   in plain words), a **Split note** (holding out a fifth of the homes
   as an honesty test — presented as a decision you're making), and
   10–18 **proposed features, each with a plain-language reason** tied
   to what the column means.
5. Untick one feature you're skeptical of, then
   **Accept features & train**.
6. **Expected:** training runs locally in seconds — a simple linear
   baseline and an upgraded model on identical preprocessing.

## 4.3 An evaluation you can argue with

7. Read the **Model evaluation**. **Expected:** it speaks dollars —
   *"typically off by $…"* — and states both models' fit, graded **only
   on the held-out homes the model never saw**. The most influential
   features are named below it in plain language.
8. Train again (open the model from the registry, train). **Expected:**
   identical metrics — same data, same seed, same result, every time.

## 4.4 Predictions are just data

9. **Expected:** a predictions dataset (one row per home: actual price,
   predicted price, holdout flag) is already in your catalog — query it,
   chart it, export it like anything else.
10. Restart the app (chapter 3.5) — the model registry and predictions
    survive.

Next: [Relational models on your data →](05-relational.html)
