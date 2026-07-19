---
layout: default
title: Tutorial 2 — ask, trust, keep
---

# 2 · Ask, trust, keep

*(features 003 Q&A + trust trail, 014 charts & exports, 015 dashboards,
016 catalog curation — these need the AI key from the setup step)*

[← Files become meaning](01-ingest.html)

## 2.1 A question, an answer, and the receipts

1. Switch to **Query** and ask, in plain English:
   *"total purchase amount by region"* (the workspace from chapter 1 —
   customers + purchases — makes this answerable via the discovered
   join).
2. **Expected:** a result table and chart, and under them the **trust
   trail**: the assumptions the agent made, the data lineage, and the
   exact SQL it ran — locally, in DuckDB. Expand it. Every number in the
   product carries these receipts.

## 2.2 When it isn't sure, it asks — and when it can't know, it says so

3. Ask something ambiguous for your workspace, e.g. *"average amount by
   status"* when two datasets carry a `status`-like column.
   **Expected:** instead of guessing, the agent asks a clarifying
   question with concrete options; pick one and the answer proceeds.
4. Ask *"what will revenue be in 2031?"* **Expected:** a plain abstention
   with a reason — no hallucinated numbers.

## 2.3 Keep it: charts, datasets, exports

5. On an answer you like, use **Save as chart**, give it a name, and
   confirm. Switch to **Charts** and open it. **Expected:** it *re-runs
   live* — saved charts are stored questions, not stale screenshots.
6. Back on the answer, use **Save result as dataset**. **Expected:** the
   result appears in the catalog, profiled like any upload.
7. Use **Export chart result as CSV** / **as Excel**. **Expected:** a
   full-fidelity download.

## 2.4 Correct the catalog's mind — and make it stick

8. On **Ingest & profile**, open a dataset whose catalog shows an open
   question ("Needs review"). **Expected:** it's a real form — pick an
   option or write a **Custom answer**, then **Submit answer**. The agent
   finishes the analysis *with your answer as ground truth*.
9. On any column description, use **Correction**, type what it really
   means, **Submit correction**. **Expected:** the description updates —
   and it is now *settled*: automation will never overwrite a
   human-settled meaning.

## 2.5 A dashboard from one sentence

10. Switch to **Dashboards**, type into **Dashboard request**:
    *"regional purchases overview: totals by region, customer count, and
    recent purchases"* → **Create dashboard**.
    **Expected:** a working grid of widgets, each with its own trust
    trail.
11. Use the region filter. **Expected:** widgets recompute *before*
    aggregation — the numbers are filtered, not the pictures.
12. Click a bar in a chart widget. **Expected:** cross-filtering — the
    other widgets follow. Click through to **drill down** to the
    underlying rows.
13. Type into **Edit dashboard request**: *"add a widget with average
    purchase amount by month"* → **Apply dashboard edit**. **Expected:**
    the dashboard gains exactly that widget.
14. Use **Print preview**. **Expected:** only the dashboard detail —
    no navigation, buttons, or trust-trail chrome — ready for
    **Print**. **Exit print preview** brings the controls back.

Next: [Databases →](03-databases.html)
