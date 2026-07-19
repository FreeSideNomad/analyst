---
layout: default
title: Tutorial 1 — files become meaning
---

# 1 · Files become meaning

*(features 001 ingestion & profiling, 006 workbench, 009 relationship
discovery, 010 workspace-aware cataloguing, 013 normalization)*

[← Tutorial home](index.html)

You'll feed the app deliberately messy real files and watch it do what a
careful analyst would: profile every column, write down what things mean,
find the joins, and ask permission before cleaning anything.

## 1.1 Ingest a messy file

1. On **Ingest & profile**, use **Upload a file** and pick
   `tutorial/data/messy_sales.csv`.
2. **Expected:** the dataset appears in the catalog within seconds,
   marked complete — despite the file's synthesized headers and mixed
   types. Open it: every column shows a profile (type, nulls, distinct
   counts, distribution), and the ingestion notes record what was messy
   and how it was handled.

## 1.2 Watch meaning arrive

3. Still on the dataset detail, read the table and column descriptions.
   With a key configured they're written by the agent from the profile
   evidence; without one, the banner says **Cataloguing without AI** and
   the text is profile-derived — either way, *never* invented from rows
   it hasn't seen: only schema, profile facts, and capped samples ever
   reach the model.

## 1.3 Two files, one workspace — links discovered and PROVEN

4. Upload `tutorial/data/customers.csv`, then `tutorial/data/purchases.csv`.
5. **Expected:** the relationships panel shows the discovered link
   `purchases.customer_id → customers.customer_id` — *not* just
   name-matched: the app checked referential integrity against the data
   (every purchase's customer exists), and marks the join required or
   optional accordingly.
6. Open the first dataset you uploaded again. **Expected:** its catalog
   entry now *knows* about the newcomers — cataloguing is
   workspace-aware and retroactive; adding `purchases` teaches the existing
   tables they are referenced.

## 1.4 Excel too

7. Upload `tutorial/data/company.xlsx`. **Expected:** each sheet becomes
   its own profiled dataset.

## 1.5 Cleanup is proposed, never done behind your back

8. Upload `tutorial/data/messy_orders.csv` — its `region` column mixes
   "East"/"east"/"EAST" and "West"/"WEST".
9. Open the dataset's **Normalization** panel. **Expected:** the app
   *proposes* a rule with evidence — the exact variant values and their
   counts — and has changed **nothing** yet.
10. Approve the rule. **Expected:** every query now sees the standard
    value. Revoke it. **Expected:** the originals return, untouched.
    That's the contract: normalization is explicit, reversible, and
    never silent.

**What you just verified:** messy ingestion, honest profiling, evidence-
based catalog text, data-validated relationship discovery, retroactive
workspace awareness, and human-gated normalization — the happy paths of
five shipped acceptance boards.

Next: [Ask, trust, keep →](02-ask.html)
