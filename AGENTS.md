# Codex Agent Notes — analyst

This repo was initialized through Claude Code plugins, especially DAE/ATDD and Superpowers. For Codex work, treat these notes as the bridge from that workflow into this environment.

## Workflow

- Follow the project constitution in `CHARTER.md`.
- Use the DAE feature artifacts as the contract: `feature.md`, `acs.md`, `spec.md`, `plan.md`, and `runbook.md` under `features/<NNN-slug>/`.
- Acceptance specs describe WHAT must work; unit tests describe HOW internals work.
- Do not edit `features/**/spec.md` merely to make tests pass.
- Do not hand-edit generated files under `features/**/.build/generated/`; regenerate them through the acceptance pipeline.
- Unimplemented acceptance steps should fail explicitly as `NOT YET IMPLEMENTED`, not be skipped or marked xfail.

## Current Feature

- Active feature: `features/001-file-ingestion-and-profiling/`.
- Current implemented slice: CSV ingestion → Parquet/DuckDB materialization → deterministic profile.
- Current in-process seam: `IngestionService(DatasetStore(...)).ingest(...)`.
- Step bindings live in `acceptance/handlers.py`.
- Acceptance generator lives in `acceptance/generator.py`.

## Commands

- Use `uv` for Python commands; do not use bare `python3` or `pip`.
- Run unit tests with `uv run pytest tests/unit`.
- Run the generated acceptance pipeline with `./run-acceptance-tests.sh`.
- Expect the full acceptance board to stay partly red until later slices are implemented.

## Architecture Constraints

- Domain code stays pure: no DuckDB, framework, API, or LLM imports in `src/analyst/domain`.
- All DuckDB/Parquet access goes through the data-engine layer under `src/analyst/engine`.
- The service layer should remain a thin orchestration facade.
- Profiling statistics should be deterministic and set-based in DuckDB.
- Raw bulk data must remain local; future LLM calls must go through a single auditable gateway with bounded samples.

## Claude Plugin Parity

- Claude plugins installed locally include `engineer`, `atdd`, `superpowers`, `crap-analyzer`, `frontend-design`, and related tools, but Codex cannot directly invoke the Claude plugin runtime unless a matching tool is exposed here.
- When a Claude plugin workflow is referenced, read its local files under `~/.claude/plugins/cache/...` if needed and reproduce the workflow using Codex tools.
- The custom `senior-engineer` Claude agent emphasizes verifying load-bearing claims against actual code/docs before giving advice; use the same standard here.
