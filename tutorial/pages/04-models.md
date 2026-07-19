---
layout: default
title: Tutorial 5 — train a model without writing code
---

# 5 · Train a model without writing code

[← Ask your data questions](03-ask.html)

Predictive models usually live behind a wall of code — notebooks,
libraries, jargon. Here, training one is a short series of decisions
you can read and confirm, on real data, with an evaluation that tells
you honestly how good (or not) the result is.

## 5.1 Real data, one click

Switch to **Models**. In the sample gallery, click **Add to workspace**
on **Ames house prices** — 1,460 real home sales from Ames, Iowa, the
classic dataset for learning price prediction. It downloads once, lands
in your catalog like any upload, and is fully profiled: 81 columns of
real-world detail.

## 5.2 Say what to predict; confirm what it may use

Under **New model**, choose the dataset, pick **SalePrice** as the
thing to predict, and click **Start**.

The app comes back speaking your language, not a library's:

- a short note explaining what predicting a price *means* for this data;
- a note explaining that a fifth of the homes will be **held back** as
  an honesty test — the model never sees them during training, so its
  score can't be flattery;
- a list of proposed inputs — columns like overall quality, living
  area, year built — **each with a one-sentence reason** why it should
  help.

You're the editor: untick anything you don't buy, then click through to
train. Training runs locally, in seconds, and always the same way — the
same data gives the same model, every time, which means results you can
reproduce and defend.

## 5.3 An evaluation in dollars, not decimals

The result reads like a sentence you could say in a meeting: *typically
off by about $X on homes it never saw*, alongside how much of the price
variation it explains — always graded only on those held-back homes.
Below it, the columns that mattered most, in plain language.

Train it again: identical numbers. If a model's quality changed every
time you re-ran it, which number would you report?

## 5.4 Predictions become ordinary data

Look in your catalog: there's a new dataset — one row per home, with the
actual price, the predicted price, and whether that home was part of
the honesty test. It's just data now: query it, chart it, put it on a
dashboard, export it. And like everything else, models and their
predictions survive a restart.

**What you can do now:** go from "I have a spreadsheet with outcomes in
it" to "I have a model I understand, with an honest score, and its
predictions are ready to use" — without writing code or trusting a
black box.

Next: [Models that understand relationships →](05-relational.html)
