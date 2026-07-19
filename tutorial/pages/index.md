---
layout: default
title: Tutorial — the whole product, hands on
---

# The analyst tutorial

This tutorial walks you through **everything the product does**, hands
on, in about an hour — and it doubles as a live re-enactment of the
acceptance criteria every feature shipped behind: each numbered step ends
in the exact observable result the test boards assert. If a step doesn't
work, that's a bug — please file it.

Everything happens either **in the browser** or through **one `make`
command** run from the `tutorial/` folder of the repository.

## Prerequisites

- Docker (Desktop is fine), `git`, `make`, and [uv](https://docs.astral.sh/uv/).
- Clone the repo and enter the tutorial folder:

```bash
git clone https://github.com/FreeSideNomad/analyst && cd analyst/tutorial
```

- **Optional but recommended** — the AI features (questions, dashboards,
  curation, model guidance) need a key in your environment before
  `make app`: either `ANTHROPIC_API_KEY=sk-ant-…` or a Claude
  subscription token `CLAUDE_CODE_OAUTH_TOKEN=…` (from `claude
  setup-token`), plus `ANALYST_CATALOG=live`. Without a key, chapters 1
  and the deterministic halves of 3–5 still work fully — the app says
  "Cataloguing without AI" instead of degrading silently.

## Start

```bash
make app     # builds the image, starts the app (:8000) + demo databases
make data    # generates tutorial/data: sample files + a cross-database pair
```

Open **http://localhost:8000**. You land on **Ingest & profile** — the
nav also shows **Query**, **Charts**, **Dashboards**, and **Models**.

## The chapters

1. **[Files become meaning](01-ingest.html)** — ingest messy real files,
   watch them get profiled and catalogued, see relationships discovered
   and *validated*, approve a data-cleanup rule. *(features 001, 006,
   009, 010, 013)*
2. **[Ask, trust, keep](02-ask.html)** — plain-English questions with a
   trust trail, saved charts, exports, dashboards from a sentence, and
   correcting the catalog's mind. *(003, 014, 015, 016)*
3. **[Databases](03-databases.html)** — connect Postgres, answers pushed
   down in place, one question across two databases, and a restart that
   loses nothing. *(005, 007, 008, 017, 011)*
4. **[Guided models](04-models.html)** — train a real house-price model
   on real data without writing code. *(012)*
5. **[Relational models on your data](05-relational.html)** — the ML
   variant: graph neural networks over linked tables, validated against
   published research, then authored on a database *you* connect. *(018,
   019)*

When you're done: `make down` stops everything (your data survives);
`make clean` removes the tutorial volumes too.

> Not covered here: team login (OAuth) — it needs your own Google or
> Microsoft app registration; see the [manual](../getting-started.html).
