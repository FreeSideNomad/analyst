# Runbook — Feature 001: File ingestion & agentic data profiling

Operator/setup steps that are not covered by automated tests. Each has an owner, an optional runnable command, and evidence of completion.

## Environment & secrets

- [ ] **human** — Provide a Claude API key for the agentic layer (Claude Agent SDK).
  - `command:` export `ANTHROPIC_API_KEY` in the app environment (never commit it; `.claude/settings.local.json` and env are gitignored).
  - `evidence:` a cataloguing call succeeds against the live model (or the live golden-eval runs).
  - Note: acceptance/unit suites use a **fake LLM** and do **not** require the key. Only the live golden-eval (AC-24) and manual smoke do.

- [ ] **agent** — Initialize the Python project with uv and pin Python 3.14.
  - `command:` `uv init` / `uv add fastapi duckdb "anthropic[...]" openpyxl charset-normalizer pytest ruff` (finalized during Slice A)
  - `evidence:` `uv run python -c "import duckdb, fastapi"` succeeds.

## Golden corpus (AC-24 fixtures)

- [ ] **agent** — Vendor the permissively-licensed small datasets into the repo test fixtures.
  - `command:` download Titanic (public), Northwind CSV (MIT), Superstore .xls (MIT) per `docs/golden-corpus.md`.
  - `evidence:` fixtures present with recorded checksums.

- [ ] **human** — Decide/authorize handling of no-license / share-alike / non-commercial datasets (Messy IMDB/HR, Olist, IMDb, etc.).
  - `evidence:` a `download_datasets` script fetches them at test time (not vendored), with attribution; legal review noted for any no-license source before shipping.

## Not applicable in feature 001
- No cloud provisioning, DNS, or deploy steps (workspace-light, no auth, no hosting yet). Auth/OAuth + deploy get their own runbooks when those features land.
