---
layout: default
title: Tutorial 1 — your first data
---

# 1 · Your first data

[← Tutorial home](index.html)

Most data tools make you clean and describe your data before they're
useful. analyst's promise is the opposite: give it your files as they
are, and *it* does the careful-analyst work — profiling, describing,
linking — while you stay in charge of every decision that matters. This
chapter shows that promise on deliberately imperfect files.

No AI key needed for anything in this chapter.

## 1.1 Upload a messy file — and get a clean picture

Download **[messy_sales.csv](files/messy_sales.csv)** — a small sales
file with the kind of flaws real exports have: "N/A" where numbers
should be, inconsistent status values, odd headers.

On **Ingest & profile**, click **Upload a file** and pick it.

Within seconds the dataset appears in your catalog. Open it and look
around: every column has been profiled — its type, how many values are
missing, how many are distinct, the shape of its distribution — and the
ingestion notes record what was odd about the file and how it was
handled. You didn't fix anything first; the flaws became *documentation*
instead of silent surprises.

## 1.2 Your data, described in sentences

Read the dataset and column descriptions on the same screen. This is the
**catalog** — the app's running understanding of what your data *means*,
written in plain sentences, built only from evidence it can point to
(the schema and the profile — never from guessing at rows it hasn't
examined). Without an AI key the descriptions are drawn directly from
the profile, and a banner says so plainly rather than pretending
otherwise.

The catalog matters because everything later — questions, dashboards,
models — reads it. The better the app's understanding, the better every
answer. And as you'll see in a later chapter, when *you* know better,
you can correct it and your word is final.

## 1.3 Two files that belong together

Download **[customers.csv](files/customers.csv)** and
**[purchases.csv](files/purchases.csv)** and upload both.

Open the relationships panel. The app has connected them:
`purchases.customer_id → customers.customer_id`. Notice what it did to
earn that arrow — it didn't just match column names; it *checked the
data*, verifying that every customer referenced by a purchase actually
exists. Name-matches that fail that check are discarded. The link also
says whether every purchase must have a customer or whether some stand
alone.

This is what lets you later ask "total purchases by region" without
ever writing a join: the app already knows how your tables fit
together, and it can prove it.

One more thing worth seeing: open `customers.csv`'s catalog entry again.
It now mentions that purchases reference it. The catalog doesn't
describe files in isolation — each table is understood in the context of
everything else you've loaded, and earlier entries update as the
picture grows.

## 1.4 Excel works the same way

Download **[company.xlsx](files/company.xlsx)** and upload it. Each
sheet becomes its own profiled dataset — same treatment, same catalog.

## 1.5 Cleanup is your call, never a surprise

Download **[messy_orders.csv](files/messy_orders.csv)** and upload it.
Its `region` column mixes "East", "east", and "EAST" — the classic mess
that quietly splits your totals into three buckets.

Open the dataset's **Normalization** panel. The app *noticed* — and
instead of fixing it silently, it shows you a proposed rule with the
evidence: the exact variant spellings and how many rows carry each. So
far it has changed **nothing**.

Approve the rule: from now on, every query sees one consistent value —
your totals add up. Now revoke it: the original values come back,
untouched. That's the contract this product keeps everywhere: it
proposes with evidence, you decide, and every decision is reversible.

**What you can do now:** hand the app any file — messy or not — and get
a profiled, described, linked, and honestly-cleaned picture of it in
minutes, without writing a line of code.

Next: [Connect your databases →](02-databases.html)
