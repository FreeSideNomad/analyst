# Runbook — Feature 005: Relational database federation

Operator/setup notes for the live federation test databases and the driver
extras. The default suites (unit + acceptance boards) need NONE of this —
they run offline against the bundled Chinook SQLite fixture.

## Live test databases (Docker)

```
make dbs-up      # start + seed all three (seed SQL cached in tests/.dbs_seed/)
uv sync --extra dbs
uv run pytest tests/live -m live -v
make dbs-down    # stop + remove volumes
```

| Engine | Image | Host port | Credentials | Sample DB | Seeding |
|---|---|---|---|---|---|
| PostgreSQL 16 | `postgres:16-alpine` | 55432 | `postgres` / `analyst` | **Pagila** (db `pagila`) | schema+data SQL from `devrimgunduz/pagila` mounted into `docker-entrypoint-initdb.d`, runs on first boot |
| SQL Server 2022 | `mcr.microsoft.com/mssql/server:2022-latest` (platform `linux/amd64`) | 51433 | `sa` / `Analyst!Passw0rd` | **Northwind** | `instnwnd.sql` from `microsoft/sql-server-samples` via in-container `sqlcmd`; the script creates objects only, so `dbs_up.sh` creates the `Northwind` DB first |
| IBM DB2 12.1 | `icr.io/db2_community/db2` (platform `linux/amd64`, `privileged`) | 50000 | `db2inst1` / `analyst` | **SAMPLE** | after boot: `docker exec analyst-dbs-db2 su - db2inst1 -c db2sampl` (idempotent) |

Live-test coordinates are env-overridable: `ANALYST_TEST_PG_HOST/PORT`,
`ANALYST_TEST_MSSQL_HOST/PORT`, `ANALYST_TEST_DB2_HOST/PORT`.

## Verified results (2026-07-03, Apple-silicon Mac, Docker Desktop 28.5.1)

**All three engines ran and passed against real sample data on this host** —
`uv run pytest tests/live -m live -v` → **13 passed** (5 Pagila, 4 Northwind,
4 DB2 SAMPLE):

- **PostgreSQL + Pagila** (ATTACH scanner): tables/profile (`actor` = 200
  rows)/composite keys (`film_actor` PK actor_id+film_id, FKs → actor/film)/
  capped fetch/clean wrong-password failure. Also verified end-to-end at the
  API layer: `POST /api/databases/connect` → 201, 22 tables as datasets
  (`film` 1000 rows, PK `film_id`), no password in any response, detach 204.
- **SQL Server + Northwind** (pymssql bridge, amd64 **under emulation —
  worked**): tables/push-down profile (`Orders` = 830 rows)/keys incl.
  composite PK on `Order Details` and FKs → Customers/Employees/Shippers/
  capped `TOP` fetch.
- **IBM DB2 + SAMPLE** (ibm_db bridge, amd64-only image **under emulation —
  worked**): tables/push-down profile (`EMPLOYEE`)/SYSCAT keys (`EMPNO` PK,
  FK → `DEPARTMENT`)/capped `FETCH FIRST` fetch.

### Apple-silicon caveats (honest observations)

- **mssql/server** has no arm64 image; under Docker Desktop's Rosetta
  emulation it booted in ~1–2 min and behaved correctly throughout.
- **DB2** is amd64-only and heavyweight: initial setup under emulation took
  ~10 minutes (watch `docker logs analyst-dbs-db2` for
  `(*) Setup has completed.`), and `db2sampl` several more. It DID complete
  and serve all live tests on this host (DB2 v12.1.3, Docker Desktop with
  Rosetta). On hosts where it fails to boot, the live tests **skip** with a
  clear reason rather than fail — the suite stays honest either way.
- First `make dbs-up` downloads images (multi-GB for mssql/db2) and seed SQL;
  both are cached afterwards.

### Real-data gotchas the live runs caught (now regression-covered)

- Pagila's `rental_by_category` **unpopulated materialized view** is surfaced
  as a table by the postgres scanner and explodes on profiling → table listing
  now pushes down `information_schema.tables … table_type='BASE TABLE'`.
- Attached postgres catalogs surface `information_schema`/`pg_catalog`
  internals via `duckdb_tables()` → listing is schema-scoped (`public`/`main`).
- T-SQL wants `SELECT DISTINCT TOP n`, not `SELECT TOP n DISTINCT` (unit-
  covered in `test_mssql_dialect_puts_top_after_distinct`).
- Fetching Pagila timestamptz values through the scanner needs `pytz`
  (added to runtime deps).
- Pagila's DDL references the `postgres` role → the container runs with
  `POSTGRES_USER=postgres`.

## Drivers (`dbs` extra)

`uv sync --extra dbs` → `pymssql` 2.3.13 + `ibm_db` 3.2.9. Both installed
clean on macOS arm64 / Python 3.14 (verified). They are optional: without
them, SQL Server/DB2 connect attempts fail with a clean 400 naming the extra;
SQLite/PostgreSQL federation needs nothing beyond default `uv sync`.

## Architecture decision record (researched 2026-07-03)

- SQLite + PostgreSQL: DuckDB core scanner extensions via `ATTACH … READ_ONLY`
  (auto-installed by DuckDB on first use; cached in `~/.duckdb`). SQLite falls
  back to a stdlib-`sqlite3` bridge if the extension can't load (offline box).
- SQL Server: a community DuckDB extension (`mssql`, hugr-lab, native TDS)
  exists but self-describes as **experimental** → driver bridge on `pymssql`
  with push-down. Revisit the scanner when it stabilizes.
- DB2: no DuckDB scanner exists → driver bridge on `ibm_db` (`ibm_db_dbi`),
  keys via `SYSCAT`.
- Governance: both paths are query-through. No Parquet/copies are ever
  written for connected tables (unit-enforced); only aggregates, capped
  samples (20) and capped fetches (200 default) leave the source.

## Human items

- None blocking. Optional: real network DB credentials for non-Docker
  verification; a decision on when to trial the community `mssql` scanner.
