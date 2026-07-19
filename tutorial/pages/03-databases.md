---
layout: default
title: Tutorial 3 — databases
---

# 3 · Databases

*(features 005 federation, 007 in-place answers, 008 files × databases,
017 cross-database joins, 011 encrypted credentials & restart)*

[← Ask, trust, keep](02-ask.html)

`make app` already started the demo databases — a Postgres seeded with
**Pagila** (the classic DVD-rental store) among them.

## 3.1 Connect a database — nothing is copied

1. On **Ingest & profile**, use **Connect a database**:
   engine `postgres`, host `host.docker.internal`, port `55432`,
   database `pagila`, user `postgres`, password `postgres`.
2. **Expected:** the connection's tables appear in the catalog within
   moments, each profiled and catalogued **in place** — the app reads
   through DuckDB's scanner; your rows never move. Declared foreign keys
   are lifted from the database's own catalog and cross-checked.

## 3.2 Answers push down

3. On **Query**, ask *"how many films per rating in pagila"*.
   **Expected:** an answer whose trust-trail SQL runs against the
   connected database — filters and joins pushed down to it, results
   assembled locally.

## 3.3 One question, a file AND a database

4. Ask a question that spans both worlds — e.g. relate a file you
   uploaded in chapter 1 to a Pagila table (region names, dates, any
   overlap the agent finds). **Expected:** a single answer whose lineage
   names both sources; the join executed locally.

## 3.4 One question, TWO databases

5. `make data` created a synthetic-but-honest pair of SQLite databases in
   `tutorial/data/`: `crm.db` and `billing.db`, sharing customer keys.
   Connect both (engine `sqlite`, path — the absolute path shown by
   `ls "$(pwd)/data"`).
6. Ask *"total billed amount by CRM segment"* (or the suggestion the
   catalog surfaces). **Expected:** one answer joining tables from **two
   different databases**, executed locally; the trust trail's SQL names
   both connections. Enterprise should total 150, smb 50.

## 3.5 Restart and lose nothing

7. From the `tutorial/` folder:

```bash
cd .. && docker compose restart analyst && cd tutorial
```

8. Reload the browser. **Expected:** every dataset, catalog entry,
   saved chart, dashboard, and **database connection** is back — the
   connections reconnected *by themselves*, because credentials are
   stored encrypted at rest (under `ANALYST_SECRET_KEY`) and replayed on
   boot. Nothing asked you to re-enter a password.

Next: [Guided models →](04-models.html)
