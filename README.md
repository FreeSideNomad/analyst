# analyst

Self-hosted **AI data analyst**: drop in Excel/CSV files or connect a database, and an agent automatically profiles, catalogues, and understands your data so anyone can ask questions in plain English — with the profiling, relationships, SQL, and assumptions always one click away.

> **Autopilot by default, grab the wheel on demand.**

Built under **DAE (Disciplined Agentic Engineering)** with **ATDD**. See [`CHARTER.md`](CHARTER.md) (engineering constitution) and [`docs/PRD.md`](docs/PRD.md) (product vision + competitive research).

## Status

Early development. Active feature: **`features/001-file-ingestion-and-profiling/`** (single-file ingestion → profiling → catalog). Slices A–B complete.

## Tech

- **Backend:** Python 3.14 (managed with **uv**), DuckDB + Parquet, FastAPI, Claude Agent SDK.
- **Frontend:** React + TypeScript, Tailwind, shadcn/ui, zustand (Swiss International Design System). *(under construction)*

## Development

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync                      # install deps (uv provisions Python 3.14)
uv run pre-commit install    # enable the local commit gate (one-time, per clone)

uv run pytest tests/unit     # unit tests
uv run ruff check .          # lint
uv run ruff format .         # format
uv run mypy src/analyst      # static types
```

### Acceptance tests (ATDD)

Given/When/Then specs live in `features/NNN-slug/spec.md`. Run the pipeline:

```bash
./run-acceptance-tests.sh
```

The board is intentionally **partly red** — unimplemented scenarios fail as `NOT YET IMPLEMENTED` and drive the remaining slices. (Requires the DAE plugin's portable parser locally; not run in CI.)

### Quality gate

The same checks run **on every commit** (`.pre-commit-config.yaml`) and **in CI** (`.github/workflows/ci.yml`): `ruff` lint + format, `mypy`, and the unit tests. Nothing lands with a lint/type/test regression.
