# Acceptance criteria — Feature 005: Relational database federation

> Checkpoint 2 (discover-acs). Vertical slice per CHARTER §6: API-contract ACs
> (HTTP-bound) + UI-flow ACs (Playwright-bound, fixtures API). Engines
> (human-specified): PostgreSQL, SQL Server, IBM DB2, with SQLite as the
> deterministic base. Federation only — nothing bulk-copied.

## A. API contract (HTTP, deterministic via the bundled SQLite sample DB)

- **AC-1 — Connect exposes tables as datasets.** `POST /api/databases/connect`
  with a valid connection registers the database under its connection name and
  every table of the source appears in `GET /api/datasets` as a dataset named
  `<connection>.<table>`, status complete.
- **AC-2 — Connected tables are profiled and catalogued in place.** Each
  connected table's dataset carries a real profile (row count, per-column
  inferred type / null count / distinct count / samples) computed through the
  federated connection, and a plain-English catalog entry (table description +
  column descriptions with roles) built without the LLM.
- **AC-3 — Declared keys are read into the catalog.** Where the source engine
  declares them, primary-key columns are marked as such and foreign-key columns
  record the table they reference, both visible in the dataset's catalog entry
  and on the connection's table listing.
- **AC-4 — Secrets never leave the server.** Connection passwords are accepted
  on connect but are never present in any API response (connect response,
  `GET /api/databases`, datasets, catalog).
- **AC-5 — List and detach.** `GET /api/databases` lists active connections
  (name, engine, reachable coordinates, table summary). `DELETE
  /api/databases/{name}` detaches: the connection disappears from the list and
  all its `<connection>.*` datasets are removed. No source data is ever
  touched.
- **AC-6 — Unreachable databases fail cleanly.** Connecting to a database that
  cannot be reached is rejected as a client error (4xx) with a clear,
  user-facing reason; never a 500.
- **AC-7 — Duplicate connection names are rejected** with a clear conflict
  error naming the connection.
- **AC-8 — Detaching an unknown connection yields not-found** naming the
  connection.

## B. Frontend flows (browser, fixtures mode)

- **AC-9 — Connect from the catalog tree.** The "Connect a database"
  placeholder is a real control: it opens a labelled form (connection name,
  engine, and either a SQLite file path or host/port/database/username/
  password), and submitting a valid SQLite connection makes the connection
  appear under "Databases" and its tables appear in the semantic catalog.
- **AC-10 — Detach from the catalog tree.** A connected database carries a
  labelled detach control; detaching removes the connection and its tables
  from the catalog tree.
- **AC-11 — A failed connection shows its reason.** Submitting an unreachable
  connection keeps the form open and shows the failure reason inline; nothing
  is added to the catalog.

## Invariants (unit-enforced, not scenario-bound)

- Federation is query-through: connecting/profiling creates **no Parquet or
  other copies** of source tables; only aggregates/samples/small result sets
  cross from the source into the local engine.
- Architecture per engine: DuckDB `ATTACH` scanners for SQLite and PostgreSQL;
  driver bridge with query push-down (pymssql for SQL Server, ibm_db for DB2)
  where no solid scanner exists. One connector abstraction covers both paths.
- Live verification against real sample DBs (Pagila / Northwind / DB2 SAMPLE
  in Docker) is `live`-marked — see `runbook.md`.
