---
layout: default
title: Tutorial 4 — ask your data questions
---

# 4 · Ask your data questions

[← Add your AI key](key.html)

This is the part the product is named for: anyone on your team asking
data questions in plain English and getting answers they can check —
not a chat that *sounds* confident, but answers that show their work.

## 4.1 Ask, then open the receipts

Switch to **Query** and ask:

> total purchase amount by region

You get a result table and a chart — built from your chapter-1 files,
joined through the customer link the app verified for you. Now the
important part: expand the panel under the answer. There's the exact SQL
that ran (locally, on your machine), the assumptions the agent made, and
where each piece of data came from.

This is why answers here are trustable where chatbot answers aren't:
you never have to take the number on faith — the reasoning is one click
away, every time, on every answer, chart, and dashboard in the product.

## 4.2 It asks when unsure — and refuses to make things up

Ask something genuinely ambiguous — for example, *"average amount by
status"* when more than one of your datasets has a status-like column.
Instead of silently picking one, the app asks you which you meant, with
concrete options. Answer, and it proceeds.

Then try *"what will revenue be in 2031?"* — it declines, and tells you
why: there's nothing in your data that can answer it. A wrong number
would have looked more impressive; the refusal is the feature.

## 4.3 Keep the good ones

- **Save as chart** on an answer you like, give it a name, and find it
  under **Charts**. Open it later: it *re-runs live* against your
  current data — saved charts are saved questions, not stale pictures.
- **Save result as dataset** turns an answer into a first-class dataset
  in your catalog — profiled and queryable, ready for follow-up
  questions on top of it.
- **Export chart result as CSV / as Excel** when the destination is a
  spreadsheet or another tool — full fidelity, no truncation.

## 4.4 One question across two databases

Remember the CRM and billing connections from chapter 2? Ask:

> total billed amount by CRM segment

One plain question; the answer joins customer segments from one
database with invoices from another, executed locally on your machine.
Open the receipts — the SQL names both connections. (Enterprise should
total 150, smb 50 — the tutorial data is small enough to check by
hand, which is rather the point.)

## 4.5 Teach the catalog what you know

The app wrote its understanding of your data; you know your business
better. Two ways your knowledge takes over:

- Where the catalog shows an open question ("Needs review"), it's a
  real form: pick an option or write your own answer and submit. The
  analysis completes *with your answer as ground truth*.
- On any description that's off, click **Correction**, say what it
  really means, and submit. The description updates — and it's now
  settled: no amount of future automation will overwrite what a human
  decided.

## 4.6 A dashboard from one sentence

Switch to **Dashboards** and type:

> regional purchases overview: totals by region, customer count, and recent purchases

A working dashboard appears — widgets, filters, the lot, each widget
with its own receipts. Try it out:

- Use the region filter: the *numbers* recompute, not just the display —
  filtering happens before aggregation.
- Click a bar in a chart: the other widgets follow (and you can drill
  through to the underlying rows).
- Type *"add a widget with average purchase amount by month"* into the
  edit box: the dashboard grows exactly that widget. Building and
  changing dashboards is a conversation, not a design tool.
- **Print preview** strips the buttons and chrome for a clean printout;
  one click brings the controls back.

**What you can do now:** give anyone on your team the ability to ask,
check, keep, and share answers about your data — without SQL, and
without ever having to trust a number blindly.

Next: [Train a model without writing code →](04-models.html)
