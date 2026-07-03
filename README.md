# analyst

Self-hosted **AI data analyst**: drop in Excel/CSV files or connect a database, and an agent automatically profiles, catalogues, and understands your data so anyone can ask questions in plain English — with the profiling, relationships, SQL, and assumptions always one click away.

> **Autopilot by default, grab the wheel on demand.**

Built under **DAE (Disciplined Agentic Engineering)** with **ATDD**. See [`CHARTER.md`](CHARTER.md) (engineering constitution) and [`docs/PRD.md`](docs/PRD.md) (product vision + competitive research).

## Status

Early development.
- **Feature 001 — file ingestion & agentic profiling**: shipped (41/41 acceptance).
- **Feature 002 — FastAPI layer & aligned frontend**: the Claude Desktop Design
  prototype integrated against the real domain (11/11 acceptance, Playwright e2e).

## Tech

- **Backend:** Python 3.14 (managed with **uv**), DuckDB + Parquet, FastAPI, Claude Agent SDK.
- **Frontend:** React + TypeScript + zustand, Vite/bun, Swiss-style design tokens (see `CONTRACT.md` for the domain↔wire contract).

## Run the app

Requires [uv](https://docs.astral.sh/uv/) and [bun](https://bun.sh).

```bash
make install     # uv sync + bun install
make dev         # API :8000 (real DuckDB store) + web :5173 together
make api-mock    # instead of `make api`: in-memory Python fixtures (demos/e2e)
```

The mock is **opt-in** (`ANALYST_FIXTURES=1`), never the default.

## Development

```bash
uv sync                      # install deps (uv provisions Python 3.14)
uv run pre-commit install    # enable the local commit gate (one-time, per clone)

uv run pytest tests/unit     # unit tests (incl. the API layer)
uv run ruff check .          # lint
uv run ruff format .         # format
uv run mypy src/analyst      # static types
cd frontend && bun run lint && bun run build   # frontend gate
```

### Acceptance tests (ATDD)

Given/When/Then specs live in `features/NNN-slug/spec.md` and are compiled to
pytest by the DAE acceptance pipeline (parser vendored under
`acceptance/vendor/`, MIT):

```bash
uv run playwright install chromium   # one-time, for the e2e suite
./run-acceptance-tests.sh            # both boards: in-process + browser e2e
E2E=0 ./run-acceptance-tests.sh      # skip the browser suite
```

Feature 001 binds steps in-process; feature 002 binds them to HTTP + Playwright
(Chromium against the production build, proxied to the fixtures API —
deterministic, no LLM).

### Quality gate

The same checks run **on every commit** (`.pre-commit-config.yaml`) and **in CI**
(`.github/workflows/ci.yml`): `ruff` lint + format, `mypy`, unit tests, the
frontend lint/typecheck/build, and both acceptance boards. Nothing lands with a
regression.
