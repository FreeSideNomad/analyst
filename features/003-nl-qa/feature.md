---
slug: nl-qa
title: Natural-language Q&A over a dataset
outcome: A user asks a plain-English question about a loaded dataset and gets a confidence-gated answer — direct when confident, an AskQuestion clarification when ambiguous — always carrying the expandable trust trail (assumptions, lineage, SQL). The real planner (semantic catalog → SQL via the Claude Agent SDK, local DuckDB execution) replaces the canned Q&A in real mode; fixtures mode stays deterministic for e2e.
status: done
merged_at: 2026-07-04
autonomy_level: high
assignee: cloud
owner: igormusic
area: query
roadmap_ref: natural-language-q-a-over-a-dataset
tracker_ref: local://nl-qa
branch: nl-qa
validation_method: "Full-stack DoD (CHARTER §6): GWT spec with API-contract + UI-e2e scenarios (Playwright on fixtures), unit tests, mypy/ruff/tsc/oxlint; LLM paths use recorded-real cassettes + opt-in live evals."
size: L
created: 2026-07-03
---

# Feature 003 — Natural-language Q&A over a dataset

> PRE-ALLOCATED STUB (parallel-session prep, 2026-07-03). Number and branch are
> fixed; the owning session fleshes this out via /engineer.prime-context →
> /engineer.discover-acs → /engineer.atdd → /engineer.plan → implement.
> Ownership boundaries + kickoff prompt: docs/PARALLEL_PLAN.md.
