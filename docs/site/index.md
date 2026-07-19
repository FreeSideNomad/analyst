---
layout: default
title: analyst — self-hosted AI data analyst
---

# analyst

**Self-hosted AI data analyst.** Drop in Excel/CSV files or connect a
database; an agent automatically profiles, catalogues, and *understands* your
data, so anyone on the team can ask questions in plain English — with the
profiling, relationships, generated SQL, and assumptions always one click
away.

> Autopilot by default, grab the wheel on demand.

![The workspace: semantic catalog + table detail](img/catalog.png)

## Get it

One self-contained Docker image — API, analytical engine (DuckDB + Parquet),
and web UI in a single container. Your data stays on your box.

```bash
docker run -d --name analyst \
  -p 8000:8000 \
  -v analyst-data:/data \
  ghcr.io/freesidenomad/analyst:latest
```

Open **http://localhost:8000**. That's it — full ingestion, profiling,
cataloguing, and relationship discovery run locally with no external calls.

To enable the LLM features (natural-language Q&A, dashboards, curation,
richer agent-written descriptions), add an Anthropic API key or a Claude
subscription token (`claude setup-token`) — governance holds regardless: only
schema, profiles, capped samples, and small result sets ever reach the model,
never your bulk data.

```bash
docker run -d --name analyst \
  -p 8000:8000 \
  -v analyst-data:/data \
  -e ANTHROPIC_API_KEY=sk-ant-... \
  -e ANALYST_CATALOG=live \
  ghcr.io/freesidenomad/analyst:latest
```

## Learn it hands-on

**[The tutorial](tutorial/)** walks the whole product end to end in about
an hour — every feature's happy path, on real data, with one `make`
command for anything the UI can't do. It doubles as a live re-enactment
of the acceptance criteria each feature shipped behind.

## The manual

1. **[Getting started](getting-started.html)** — run the container, configure
   keys, first login.
2. **[Ingest & profile](ingest.html)** — files, connected databases, the
   semantic catalog, relationships.
3. **[Ask questions](ask.html)** — plain-English Q&A, clarifications, the
   trust trail, saved charts, exports, dashboards, cross-database questions.
4. **[Guided models](models.html)** — train a prediction model through
   decisions, not code: real sample data on demand, agent-proposed features,
   deterministic local training, honest evaluation.
5. **[Administration](admin.html)** — data governance, credential storage,
   workspaces, backups.

## Why it's different

- **Agentic ingestion & auto-cataloguing** — types, nullability, cardinality,
  distributions, plain-English column meanings, and discovered
  primary-/foreign-key relationships (validated against the data, not just
  name-matched), built into a persistent semantic layer per workspace.
- **Workspace-aware meaning** — each new table is catalogued *knowing* the
  tables already there; adding `orders` teaches the existing `customers` that
  it is now referenced.
- **Confidence-gated answers** — the agent answers directly when it's sure
  and asks a clarifying question when it isn't (two candidate "region"
  columns, say).
- **Trust trail on every answer** — assumptions, data lineage, and the exact
  SQL, expandable under every result, chart, and dashboard widget.
- **Keep what matters** — answers become saved charts that re-run live;
  dashboards assemble from a sentence and stay filterable, cross-filtering,
  and printable; everything exports (CSV/Parquet/Excel) at full fidelity.
- **You own the meaning** — normalization rules and catalog corrections are
  proposed with evidence and only ever applied by you; human-settled
  meanings are never overwritten by automation.
- **Real governance** — SQL executes locally in DuckDB; connected databases
  are queried read-only in place (nothing copied); credentials are encrypted
  at rest under an operator-supplied key.

<sub>Source: [github.com/FreeSideNomad/analyst](https://github.com/FreeSideNomad/analyst) ·
built with DAE/ATDD — every feature ships behind an executable acceptance
board.</sub>
