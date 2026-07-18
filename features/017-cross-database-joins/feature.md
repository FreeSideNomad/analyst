---
slug: cross-database-joins
title: Joins across multiple connected databases
outcome: One plain-English question can join tables living in TWO different connected databases — "which customer segment generates the most revenue?" where customers live in the CRM database and invoices in the billing database. The join executes locally in DuckDB over both attachments (nothing is copied between the remote systems; the standing governance invariant holds — only capped results and metadata leave the box), the trust trail's SQL names both connections, relationship discovery surfaces the cross-database key that makes the join plannable, and the capability survives restart + credential-based reconnect (011). Single-database behavior is unchanged. Ships with a deterministic synthetic two-database sample kit (generator script) because join mechanics need controlled keys, not organic signal.
status: done
autonomy_level: high
assignee: local
owner: igormusic
area: query
roadmap_ref: cross-database-joins
tracker_ref: local://cross-database-joins
branch: cross-database-joins
validation_method: "Acceptance board over two synthetic SQLite connections: NL question answers via a cross-DB join (planner cassette, recorded live) with exact totals; discovery pins the cross-DB relationship; restart/reconnect keeps it answerable; a question over a detached database fails safe. Mutation gates on federated discovery and on the planner's multi-connection table view."
size: M
created: 2026-07-18
---

# Feature 017 — Cross-database joins

> Promoted from roadmap item `cross-database-joins` (the 008 residual: file×DB
> pushdown shipped there with cross-*multiple*-DB joins explicitly out).
> Probe 2026-07-18 (this session): the ENGINE already executes
> two-connection joins locally and discovery already finds the cross-DB key —
> this feature makes the NL path deliver it, pins the whole contract, and
> ships the sample kit.

Scope sketch (fixed at discover-acs):
- Planner: both connections' queryable tables + the cross-DB relationships
  reach planning; a segment-revenue question yields a two-connection join.
- Execution stays the feature-007 local scanner path (both sides ATTACHed);
  no new pushdown machinery.
- Synthetic kit: `scripts/make_cross_dbs.py` → crm.db (customers: id, name,
  segment, region) + billing.db (invoices: id, customer_id, amount, issued)
  with exact, documented totals.
