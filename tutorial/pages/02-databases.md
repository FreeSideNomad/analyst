---
layout: default
title: Tutorial 2 — connect your databases
---

# 2 · Connect your databases

[← Your first data](01-first-data.html)

Files are half the story; most real data lives in databases. analyst
connects to them **in place** — it reads through the connection, nothing
is copied out, and the same profiling and cataloguing you saw for files
happens for every table behind the connection.

For the tutorial we ship three small databases as ready-made Docker
images (so you don't have to set anything up). Start them:

```bash
docker compose --profile databases up -d
```

That adds a Postgres loaded with **real banking data** — the public
PKDD'99 "Berka" dataset: nine linked tables covering accounts, loans,
cards, and about a million transactions from a real (anonymized) bank —
plus a small **CRM** and a small **billing** database that share
customer keys.

## 2.1 Connect the bank

On **Ingest & profile**, click **Connect a database** and enter:

| field | value |
|---|---|
| engine | `postgres` |
| host | `berka-db` |
| port | `5432` |
| database | `berka` |
| user | `postgres` |
| password | `tutorial` |

Within moments, all nine tables appear in your catalog — profiled and
described like your uploads were, but **without the data moving**: the
app reads through the connection on demand. A million-row transactions
table is now part of your workspace, and your Postgres is still the only
place it lives.

Open the relationships view: the links between the bank's tables
(accounts to transactions, loans to accounts, cards to dispositions…)
are all there — the ones the database itself declares, *plus* ones
discovered and verified against the data, the same way your CSVs were
linked in chapter 1.

## 2.2 Connect the CRM and billing pair

Connect two more, same form: host `crm-db`, database `crm`; then host
`billing-db`, database `billing` (user `postgres`, password `tutorial`
for both).

These two systems come from different worlds — a CRM with customer
segments, a billing system with invoices — but they share customer
keys, and the app finds that link **across the two connections**. Check
the relationships view: customers in one database, invoices in another,
connected and data-verified. In a later chapter you'll ask one plain
question that spans both.

## 2.3 Restart everything — lose nothing

The skeptic's test. Restart the app:

```bash
docker compose restart analyst
```

Reload the browser. Everything is back: your uploaded datasets, the
catalog and its descriptions, your approved cleanup rule — and all
three database connections, **already reconnected**. You didn't
re-enter a single password: credentials are stored encrypted on your
machine (under a key you control) and replayed at startup.

**What you can do now:** bring your actual databases — Postgres,
SQLite, SQL Server, DB2 — into the same workspace as your files, with
nothing copied and nothing to re-configure after a restart.

Next: [Ask your data questions →](03-ask.html)
