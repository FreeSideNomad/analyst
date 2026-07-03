---
slug: db-federation
title: Relational database federation
outcome: A user connects a relational database (Postgres/MySQL/SQLite) and its tables become queryable and profiled through DuckDB ATTACH — federated, nothing copied. The 'Connect a database' UI becomes real; declared PK/FK relationships are read into the catalog.
status: ready
autonomy_level: high
assignee: cloud
owner: igormusic
area: ingestion
roadmap_ref: relational-database-ingestion
tracker_ref: local://db-federation
branch: db-federation
validation_method: "Full-stack DoD (CHARTER §6): GWT spec with API-contract + UI-e2e scenarios (Playwright on fixtures), unit tests, mypy/ruff/tsc/oxlint; LLM paths use recorded-real cassettes + opt-in live evals."
size: L
created: 2026-07-03
---

# Feature 005 — Relational database federation

> PRE-ALLOCATED STUB (parallel-session prep, 2026-07-03). Number and branch are
> fixed; the owning session fleshes this out via /engineer.prime-context →
> /engineer.discover-acs → /engineer.atdd → /engineer.plan → implement.
> Ownership boundaries + kickoff prompt: docs/PARALLEL_PLAN.md.
