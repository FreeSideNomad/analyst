# CHARTER — analyst

> The project constitution. Every DAE checkpoint reads this. Changes are PR'd and human-approved.
> Status: **APPROVED** (Checkpoint 0 / onboard, signed off 2026-07-01)

---

## 1. Methodology

This project is developed under **DAE (Disciplined Agentic Engineering)** with **ATDD** at its core.

- Every feature moves through the pipeline: `discuss → feature-init → discover-acs → atdd (specs + pipeline) → plan → implement → refine → verify/harden`.
- **Acceptance-first:** Given/When/Then specs describe external observables in domain language *before* code. No implementation leakage into specs.
- **Two parallel test streams:** acceptance tests (verify WHAT) + unit tests (verify HOW). Mutation testing is the third layer (verify the tests catch bugs).
- **Definition of covered:** a feature is fully ATDD-covered when its folder has `feature.md`, `acs.md`, `spec.md` (+ `.build/spec.json` IR), and generated acceptance tests that pass against the code.

## 2. Architecture

`analyst` ingests tabular data (Excel/CSV) and relational databases, profiles and catalogues it via **agentic workflows**, stores it as queryable **Parquet** managed by **DuckDB**, and answers natural-language questions over the resulting dataset collection — producing exports, visualizations, and dashboards.

**Layers (dependencies point inward/downward only):**

1. **Domain / core** — dataset, column, profile, relationship (PK/FK), normalization-rule, catalog entities. Pure Python, no I/O, no framework imports.
2. **Data engine** — DuckDB + Parquet. Files (Excel/CSV) are materialized to Parquet; relational databases are **attached and queried through (federated) — never copied**. Ingestion pipeline: source → profiling → catalog. All bulk computation runs locally in DuckDB.
3. **Agentic layer** — **Claude Agent SDK**, prompt-driven. Owns: ingestion analysis, data profiling (nullability, distributions), PK/FK discovery **including validating candidate relationships when none are formally declared**, normalization detection (case standardization — upper/lower/proper — and beyond), dataset/attribute cataloguing, NL→query answering, and dashboard authoring. Latest Claude models. **Whenever confidence is low, it emits a structured clarification (the AskQuestion primitive) rather than guessing** — a cross-cutting contract the frontend renders as native multiple-choice UI.
4. **API** — **FastAPI** (latest Python, `uv`-managed). Exposes ingestion, catalog, query, and export/visualization endpoints. Thin — orchestrates the layers below; no business logic.
5. **Frontend** — **React + TypeScript**, **Tailwind**, **shadcn/ui**, **zustand** state, styled per the **Swiss International Design System** (grid discipline, Helvetica-family type, restrained palette, functional clarity).

**The semantic catalog is the spine.** Per-workspace, agent-built, human-curatable: table/column descriptions, discovered + test-validated relationships, metrics, synonyms. Query planning targets the catalog, not raw schema — this is the primary accuracy and trust lever (see PRD §2, §8).

**Persistence.** Single-image, embedded, no separate DB container. App/transactional state (users, workspaces, permissions, catalog metadata, conversations) → SQLite; analytical data → DuckDB/Parquet. (v1 recommendation; confirmable at architecture planning.)

**Governance boundary (hard invariant).** Only schema, profiles, small samples, and small result sets cross to the Claude API. **Raw bulk data never leaves the box.** What is sent to the model must be auditable/logged.

**Key architectural rules:**
- Domain core never imports the data engine, agentic layer, or FastAPI.
- The agentic layer is prompt-driven and testable: prompts and their expected structured outputs are versioned artifacts.
- All Parquet/DuckDB access goes through the data-engine layer — no raw DuckDB calls from API or agentic code.
- Ingestion is idempotent and profiling is reproducible for a given source snapshot.
- Discovered relationships and normalization rules are **test-validated candidates**, never silently applied — a wrong join corrupts every downstream answer.

## 3. Conventions

**Backend (Python):**
- **`uv` for everything** — running, dependency management, virtualenvs. Never bare `python3` or `pip`. (Project rule, also in user memory.)
- Latest Python (3.14.x on this machine). Full type hints. `ruff` for lint+format. `pytest` for tests.
- Modules organized by layer (§2). Files stay small and single-responsibility.

**Frontend (TypeScript/React):**
- Functional components, hooks, `zustand` stores for state. `shadcn/ui` primitives; Tailwind utility classes. Swiss-design tokens centralized.
- Strict TypeScript. Component-per-file.

**Cross-cutting:**
- Conventional-commit-style messages. One feature per branch (`feature/<slug>`).
- Structured, versioned prompts for all agentic workflows.

## 4. Scope

**In scope (product vision):**
- Ingest Excel & CSV files; ingest relational databases.
- Deep ingestion: column/type analysis **plus** data profiling (nullability, cardinality, value distributions).
- PK/FK relationship use and **discovery/validation** of candidate relationships not formally declared.
- Normalization-need detection (case standardization and similar) with proposed rules.
- DuckDB/Parquet catalog of datasets and their attributes, built by agentic cataloguing.
- Natural-language Q&A over the loaded dataset collection, with ambiguity resolved via the structured **AskQuestion** primitive (confidence-gated, native React multiple-choice).
- Data exports and charts.
- **Interactive dashboards** (Tableau-like): agent-authored, then filterable/re-visualizable, built and refined through the agentic AskQuestion workflow.

**MVP (first slice — to be confirmed at feature triage):**
- Single-file Excel/CSV ingestion → profiling → Parquet + catalog entry → answer NL questions over that one dataset.
- RDBMS ingestion, cross-dataset joins via discovered FKs, and dashboards come as later features.

**Out of scope (for now):** multi-tenant SaaS concerns, real-time streaming ingestion, non-tabular (image/audio) data.

## 5. Agent team

Default DAE roles for this project:
- **spec-writer** — authors GWT acceptance specs.
- **spec-reviewer / spec-guardian** — audits specs for implementation leakage.
- **engineer** — implements against specs (TDD).
- **refiner** — cleans up implemented code before verification.
- **verifier** — hardens, runs mutation testing, confirms coverage.

Single-repo project; roles run as fresh agents per checkpoint to prevent role erosion.

## 6. Quality stance

- **Goal:** full ATDD coverage of every feature. New features are born covered by going through the pipeline.
- Unit-test coverage target: **≥ 80%** on changed code (backend); frontend components tested at the store/behavior level.
- **Mutation testing** on core/data-engine logic; target mutation score to be set in the manifest (start pragmatic, tighten over time).
- Acceptance tests must pass against real code before a feature is "done."
- Agentic workflows validated with recorded/mocked model interactions where determinism matters; live-model checks gated behind explicit runs.

## 7. Autonomy stance

**Full autonomy** (human decision at onboard).

- Agents may drive features end-to-end through the pipeline and open PRs.
- **Caveat on record:** the validation surface is currently thin — no staging, monitoring, or feature-flag infrastructure exists yet, and there is no git remote/origin (cloud-agent dispatch stays local until one is added). Full autonomy is granted regardless, per human decision.
- **Recommended upstream backlog items to support the stance:** stand up a staging environment + monitoring, add a git `origin` (GitHub — `gh` is installed) to enable remote-agent dispatch, and adopt a feature-flag tool for safe rollout.
