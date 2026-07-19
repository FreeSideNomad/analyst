---
layout: default
title: Tutorial — the whole product, hands on
---

# The analyst tutorial

**analyst** is a self-hosted AI data analyst: drop in files or connect
your databases, and it profiles everything, writes down what your data
means, finds how tables relate, and lets anyone ask questions in plain
English — with the reasoning and SQL always one click away, and your
data never leaving your machine.

This tutorial takes you through all of it, hands on, in about an hour.
**You need Docker, a browser, and a Claude token.** Nothing to clone,
nothing to install.

## Get your Claude token

analyst's analysis is done by Claude — cataloguing, questions,
dashboards, model guidance all use it. Bring a token before you start:

- **Claude subscription (recommended).** If you have a Claude Pro/Max
  subscription and the [Claude CLI](https://claude.com/claude-code)
  installed, run:

  ```bash
  claude setup-token
  ```

  Log in when it asks, and it prints a long-lived token starting with
  `sk-ant-oat…`. That's your `CLAUDE_CODE_OAUTH_TOKEN`.

- **Anthropic API key.** Alternatively, create a key (`sk-ant-api…`) at
  [console.anthropic.com](https://console.anthropic.com) and use it as
  `ANTHROPIC_API_KEY` instead.

**What Claude can and cannot see.** The model is never handed your data
wholesale. It sees table schemas, profile summaries, the catalog's
descriptions, small capped samples, and the small result sets of
queries — enough to reason about your data's *shape and meaning*. The
queries themselves run locally, and your bulk data never leaves your
machine.

## Start the app

Export the token in the shell you'll run Docker from, then download the
tutorial's compose file and start it:

```bash
export CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat...   # or: export ANTHROPIC_API_KEY=sk-ant-api...
curl -O https://freesidenomad.github.io/analyst/tutorial/docker-compose.yml
docker compose up -d
```

Open **http://localhost:8000**. You're looking at the workspace: the
catalog on the left (empty for now), and tabs for **Ingest & profile**,
**Query**, **Charts**, **Dashboards**, and **Models**.

> Already ran the app before? Docker won't re-pull a tag it has cached —
> run `docker compose pull` first to make sure you're on the current
> image.

## The chapters

1. **[Your first data](01-first-data.html)** — upload real (and
   deliberately messy) files; watch them get profiled, described, and
   linked together; approve a data cleanup instead of having one done
   behind your back.
2. **[Connect your databases](02-databases.html)** — plug in a Postgres
   with a million rows of real banking data, plus a small CRM and
   billing pair; see everything catalogued in place, nothing copied —
   and restart the app to see that nothing is lost.
3. **[Ask your data questions](03-ask.html)** — plain English in,
   answers with receipts out; keep the good ones as live charts and
   dashboards; correct the catalog when you know better.
4. **[Train a model without writing code](04-models.html)** — a real
   house-price model on 1,460 real home sales, built from decisions you
   confirm, evaluated honestly in dollars.
5. **[Models that understand relationships](05-relational.html)** — the
   ML edition: models that learn from how your tables connect, trained
   on real banking data — including on a database *you* connect.

When you're done: `docker compose down` stops everything (your data
survives in Docker volumes); add `-v` to remove the data too.

> Team login (Google/Microsoft) isn't part of the tutorial — it needs
> your own OAuth app registration. See the
> [manual](../getting-started.html) when you're ready for that.
