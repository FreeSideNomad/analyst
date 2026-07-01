---
slug: file-ingestion-and-profiling
title: File ingestion & agentic data profiling
outcome: A single Excel/CSV file added to a workspace is auto-profiled, materialized to Parquet/DuckDB, and turned into a revealable, editable semantic catalog entry — fully automatic.
status: ready
autonomy_level: high
assignee: local
owner: igormusic
area: ingestion
roadmap_ref: file-ingestion-agentic-data-profiling
tracker_ref: local://file-ingestion-and-profiling
branch: file-ingestion-and-profiling
validation_method: "Local manual smoke via API/CLI — ingest representative clean + messy CSV and XLSX samples; assert profiling stats, Parquet/DuckDB registration, and catalog entry match expectations; confirm the LLM-egress log contains only schema/profiles/samples (governance invariant). No staging yet."
size: L
created: 2026-07-01
---

# Feature 001 — File ingestion & agentic data profiling

> Checkpoint 1.5 (Ready contract). MVP foundation. See `docs/PRD.md` §8.1–8.2, principle 4–6.

## Outcome

A user adds a single **Excel or CSV file** to a workspace. The system, **on autopilot**:
1. Reads the file and infers a clean tabular schema.
2. **Profiles every column** — inferred type, null rate, cardinality, distinct/sample values, numeric min/max/quantiles, and a value-distribution summary.
3. **Materializes** the data to **Parquet**, registered as a **DuckDB-queryable** table.
4. Uses the agent (Claude Agent SDK) to write **plain-English table + column descriptions** and infer column roles, assembling a **semantic catalog entry** for the workspace.
5. Persists that catalog entry in a **structured, editable** form.

This is the foundation the confidence-gated NL Q&A feature (002) builds on.

## Scope

**In:**
- Single-file ingestion for **CSV** and **Excel** (`.xlsx`).
- Deterministic column profiling (types, null rate, cardinality, distinct/sample values, numeric quantiles, distribution summary).
- Materialization to Parquet + DuckDB table registration.
- Agentic cataloguing: agent-generated table/column descriptions and inferred roles → structured semantic catalog entry.
- **Governance invariant enforced + logged:** only schema, profiles, and small samples are sent to the LLM; raw bulk data never leaves the box.
- The **AskQuestion primitive contract** (backend side) for ambiguous profiling decisions (e.g. ambiguous type/role) — structured clarification emitted for the caller to resolve. UI rendering is later (frontend horizon).
- Catalog entry is **editable** at the API/data-model level (grab-the-wheel curation groundwork).

**Out (deferred to other features):**
- NL query answering / SQL generation → **feature 002**.
- PK/FK relationship discovery & validation → needs multiple sources; **next** horizon.
- Normalization *rule application* (detection may surface suggestions; applying/altering values is deferred).
- Relational-DB federation → **next** horizon.
- Multi-file / multi-sheet-as-relations handling beyond a single table.
- Frontend reveal/edit UI, interactive dashboards → **later** horizon.
- **Auth (Google/MS OAuth) + real multi-workspace permissioning** → separate foundational feature (see Dependencies). This feature assumes a single default workspace context.

## Context & sources

- `docs/PRD.md` — §2 (semantic catalog as spine), §8.1 (ingestion & cataloguing), §8.2 (curation), §9 (architecture), §10 (governance).
- `.engineer/roadmap.md` — item `file-ingestion-agentic-data-profiling` (now, priority 1).
- `CHARTER.md` — §2 architecture layers, governance boundary invariant.

## Dependencies & flags

- **Auth/workspace gap:** the product needs Google/MS OAuth + first-user-admin workspace permissioning (PRD §8.4), which is **not yet a roadmap feature**. This feature is scoped **workspace-light** (a single default/implicit workspace, no auth) so it is independently buildable and testable. Recommend adding an **"Auth & workspaces"** foundational feature to the roadmap.
- **Governance/eval harness:** the "only metadata/samples leave the box" invariant needs an egress log + an assertion mechanism from day one.

## Open questions (carried from PRD)

- LLM-led vs statistics-led inference for column roles/types on messy real-world files — validate empirically.
- How agent-generated descriptions handle low-quality/ambiguous columns without over-asserting.

## Validation

Per frontmatter `validation_method`: local manual smoke via API/CLI on representative clean + messy CSV/XLSX, plus the acceptance + unit (+ mutation) suites the ATDD pipeline generates. Governance invariant is a first-class test: assert the LLM-egress log never contains bulk rows.
