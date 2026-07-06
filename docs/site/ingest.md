---
layout: default
title: Ingest & profile
---

# Ingest & profile

[← Manual home](index.html)

## Add data

Click **＋ Add data** — upload a file or connect a database.

![Add data menu](img/add-data.png)

**Files:** CSV, TSV, Excel (one dataset per sheet), and JSON. Ingestion
materializes the data to Parquet/DuckDB, profiles every column (type,
nullability, cardinality, ranges, value distributions), and catalogues the
table — descriptions, column roles, and relationships — automatically.
Messy files are handled: synthesized headers, duplicate columns, mixed
types, and encodings are detected and recorded, never silently mangled.
Refreshing a dataset with new data validates it against the established
schema first.

## The semantic catalog

Every table gets a plain-English meaning, not just a schema dump:

![Table detail: description, relationships, column meanings](img/catalog.png)

- **Descriptions** for the table and every column, grounded in the actual
  values ("References a customer record", "4 distinct regions").
- **Roles** — identifier, metric, category, date — drive how questions are
  answered.
- **Relationships** — primary-/foreign-key links are *discovered*, even when
  nothing is declared: candidate keys are proposed by name and type, then
  **validated against the data** (every child value must exist in the
  parent). Declared database keys, composite keys, and cross-source links
  (a CSV referencing a database table) are all first-class citizens.
- **Workspace-aware meaning** — a new table is catalogued knowing the tables
  already present, and the tables it links to are updated to mention it.

Everything the agent writes is revealable and editable — autopilot by
default, grab the wheel on demand.

## Connect a database

![Connect a database](img/connect-database.png)

PostgreSQL, SQLite, SQL Server, and IBM DB2. Connections are **federated**:
nothing is copied — queries read through to the source (read-only), so use a
read-only account. Tables are profiled and catalogued like files and appear
in the same catalog; questions can join *across* files and databases.

With the operator key configured ([Getting started](getting-started.html)),
credentials are encrypted and remembered: after a restart your databases
reconnect by themselves, showing their previously derived catalog instantly.
A database that's down shows as **unreachable** with a Retry button — its
meaning stays visible, and retrying never asks for the password again.

Next: [Ask questions →](ask.html)
