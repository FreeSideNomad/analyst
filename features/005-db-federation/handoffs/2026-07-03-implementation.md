# Handoff — Feature 005: Relational database federation (implementation complete)

Date: 2026-07-03 · Branch: `db-federation` (worktree) · Status: **done, ready for PR by integrator**

## What shipped

A user connects PostgreSQL / SQL Server / IBM DB2 / SQLite; every table
becomes a profiled, catalogued, queryable dataset **through federation** —
queried in place, never copied.

- **Domain** `src/analyst/domain/connection.py` — engines, `ConnectionSpec`
  (secret held server-side only), `TableKeys`/`ForeignKey`, deterministic
  LLM-free `catalog_for_table` (declared PK/FK read into the catalog).
- **Engine** `src/analyst/engine/federation.py` — one `Connector` protocol,
  two paths: DuckDB `ATTACH … READ_ONLY` scanners (sqlite, postgres; reuses
  the feature-001 profiler) and a driver **bridge** with SQL push-down
  (pymssql → SQL Server, ibm_db → DB2, stdlib-sqlite fallback/test double).
  `FederationService` registry: connect/list/tables/fetch(capped)/detach.
- **API** `src/analyst/api/routes/databases.py` — connect/list/detach;
  response models have no password field by construction; reset-aware manager
  (fresh `/api/_reset` ⇒ fresh connections). Datasets named `<conn>.<table>`.
- **UI** — the CatalogTree "Connect a database — soon" placeholder is a real
  flow (`frontend/src/components/DatabasePanel.tsx` + `api/databases.ts`):
  labelled connect form (engine, SQLite path or host/port/db/user/password),
  connection list with engine badge + detach, inline `role=alert` failure.
- **Fixtures/e2e** — bundled Chinook subset `tests/golden/chinook.sqlite`
  (MIT; generator `tests/golden/make_chinook.py`); `acceptance/e2e_005.py`
  on `e2e_base`; `.handlers` → `acceptance.e2e_005`.
- **Live Docker stack** — `docker-compose.dbs.yml` + `make dbs-up/dbs-down`
  (+ `scripts/dbs_up.sh` seeding) with Pagila / Northwind / DB2 SAMPLE;
  `tests/live/test_federation_dbs.py` (`-m live`).

## Verification (all runs on 2026-07-03)

- Boards: 001 = **41**, 002 = **13**, 005 = **11** — all green.
- `uv run pytest tests/unit -q` → **94 passed**.
- `uv run pytest tests/live -m live -v` → **13 passed** — ALL THREE engines
  verified against real Docker sample DBs on the Apple-silicon host (mssql
  and DB2 under amd64 emulation; DB2 setup ~10 min). Details + gotchas the
  live runs caught: `runbook.md`.
- mypy clean, ruff check+format clean, `bun run lint` + `bun run build` clean.

## Shared-file touches (for the integrator)

- `src/analyst/api/app.py` — databases router include only.
- `src/analyst/api/repository.py` — `add_records`/`remove_records` hooks.
- `frontend/src/stores/catalog-store.ts` — connections state + actions.
- `frontend/src/pages/WorkspacePage.tsx` — placeholder → `<DatabasePanel />`.
- `Makefile` — `dbs-up`/`dbs-down` targets. `.gitignore` — `tests/.dbs_seed/`.
- `pyproject.toml` — `pytz` runtime dep, optional `dbs` extra
  (pymssql/ibm-db), mypy override for the two driver modules.

## Follow-ups / notes for later features

- Feature 009 (cross-dataset joins) may want federated relations attached
  into the shared `DatasetStore` DuckDB rather than per-connection in-memory
  cons — deliberate v1 isolation choice, easy to lift via `FederationService`.
- Community `mssql` DuckDB extension is experimental today; revisit as a
  scanner replacement for the bridge when it stabilizes.
- Bridge profiles omit quantiles (engine-portable push-down); scanner path
  has full parity with file profiling.
