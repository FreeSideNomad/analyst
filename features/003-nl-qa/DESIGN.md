# Design note — Query & Federation architecture

> Consolidated from the design discussion of 2026-07-04. Anchored in feature 003
> (NL Q&A) because that is where querying lives; it spans the phased federation
> work (features 007/008) and informs 005 (DB connections) and 006 (workbench).
> This is a **design record**, not an ADR — it captures decisions + rationale so
> they survive the chat. Update it as the design evolves.

## 1. Engine choice — DuckDB (with eyes open)

DuckDB is the query engine: embedded, single-node, single self-contained
container, Python-native, first-class file+analytics ergonomics, zero infra —
the only option that satisfies the product's "self-hosted single Docker image"
principle while federating files + relational DBs.

**Honest ceiling** (per MotherDuck's own guidance): cross-source joins execute
*in DuckDB in memory* — pushdown of projections/filters is reliable, join
pushdown is not — so it is a poor fit for >1 TB joins, sub-100 ms latency, or
high concurrency. Our workload (team-scale, rollups + exploration) sits in its
sweet spot.

**Exit signals** (make switching a conscious choice, not a default): large
federated joins, many concurrent users, or a need for first-class MSSQL/DB2
pushdown → migrate to **Apache DataFusion + datafusion-federation** (embedded,
keeps single-container, can push whole sub-plans incl. same-source joins to the
source) or **Trino** (true distributed federation + mature MSSQL/DB2 connectors,
but trades away single-container). Landscape surveyed: DuckDB, DataFusion,
Trino, ClickHouse/chDB, Postgres-FDW, Spark, Polars.

## 2. Connectivity & OSS licensing per engine

- **PostgreSQL / SQLite / MySQL** — DuckDB has native scanners (`ATTACH TYPE
  postgres`, …): projection + filter pushdown, joins in DuckDB. Fully OSS.
- **SQL Server** — solvable 100% OSS: `pymssql`+FreeTDS (LGPL, current bridge),
  Microsoft's MIT-licensed `mssql-jdbc`, or the DuckDB native-TDS community
  extension / official `odbc-scanner` + FreeTDS. Upgrade path: the native-TDS
  extension for real pushdown.
- **IBM DB2** — the hard case. No clean-room OSS driver exists; the only path is
  `ibm_db` (Apache-2.0 *wrapper*) over IBM's **proprietary-but-free** CLI driver.
  **Free for Db2 LUW** (our Docker `SAMPLE`); **licensed (not free)** for Db2
  z/OS and Db2 for i (AS/400) — needs a Db2 Connect license. Document this in the
  federation runbook. If "zero proprietary components" is ever a hard rule, DB2
  is the one source that can't fully satisfy it — that's IBM's ecosystem.

## 3. How DuckDB's scanner actually works (so nobody expects magic)

A scanner lets DuckDB `ATTACH` a foreign DB and read its tables live at query
time, pushing **column selection** and **single-table filters** down to the
source (so only the needed slice crosses the wire), but the **joins/aggregations
run in DuckDB's own single-node engine in memory**. It is NOT a distributed/MPP
planner. A join between a local file and a remote table can only run where both
are visible — DuckDB — so that part is irreducibly local. "Join in memory" ≠
"download the table": pushdown keeps the pull small.

## 4. Federation strategy — "always remotely" via LLM SQL templates

**Rejected:** attaching the remote into an ephemeral in-memory overlay and
joining in DuckDB. Even in-memory it is fiddly, and the naive persistent-attach
variant would write the source DSN (password) into `catalog.duckdb` on disk (a
C3-class leak) and hang on restart.

**Chosen:** the LLM generates a **SQL template**; the runtime injects local
file values from a DuckDB **provider query** and runs the finished SELECT
**on the remote**. DuckDB computes the small local side + holds the result; the
remote does the join with its own indexes. Nothing is attached, no DSN persists,
and the query that runs on the source is a normal, reviewable SQL statement.

### The plan contract

The planner emits `sql_template` + `bindings[]` instead of inlined data:

```jsonc
{
  "action": "answer",
  "sql_template":
    "SELECT c.first_name, c.last_name, v.tier
     FROM customer c JOIN {{vip}} v ON v.customer_id = c.customer_id",
  "bindings": [
    { "name": "vip", "expand": "values",
      "provider": "SELECT customer_id, tier FROM orders_vip",
      "columns": ["customer_id", "tier"] }
  ],
  "assumptions": [...], "lineage": [...]
}
```

Runtime: run each provider on DuckDB → **cap** → **dialect-render + parameterize**
→ substitute → validate → run on the remote (read-only) → capped result.

Two expansion kinds, both read-only:
- `in_list` — provider returns one column → `{{ids}}` → `(1,2,5)`
- `values` — provider returns rows → `{{name}}` → `(VALUES …) AS name(cols)`

### Locked decisions

1. **The LLM picks the expansion strategy** (`in_list` vs `values`) — that is the
   payoff of profiling + semantic discovery: it has row counts/cardinality/types
   to choose. The runtime enforces the cap; it does not override the choice.
2. **Cap `N = 100,000` rows, configurable. No write path, ever.** Inline up to N;
   beyond N is an **explicit limitation surfaced to the user** — never a silent
   temp-table write, never a silent huge pull. (Temp tables would need DDL/write
   on the source, breaking the read-only guarantee, and would push our data onto
   their server — a governance inversion. Ruled out.)
3. **The final SQL always runs on the remote**, read-only.
4. **Trust trail shows the template (unexpanded).** Values aren't secret (the
   user sees results anyway); the template is the reviewable artifact.

### Why this is safer *and* more explainable
- Bulk values flow from a DuckDB result through **deterministic parameterized
  rendering** — never through the model, never as LLM-authored SQL text — so the
  prompt-injection-via-cell-value vector largely evaporates.
- The template is a first-class, auditable artifact: trust trail shows template +
  provider query + row count + final SQL — no opaque engine "dynamic filtering."
- This is the deliberate, controlled form of what mature engines do automatically
  (Trino dynamic filtering, Oracle bloom-filter pushdown).

### Validation splits cleanly
- **Provider queries** run on our DuckDB → the **C2 closed-world AST guard**
  applies (only known datasets; no table functions / file paths).
- **The remote template** → validated as a single **read-only SELECT** with
  **parameterized** value injection; runs under a read-only connection bounded by
  the user's own DB permissions.

## 5. Result handling

- **≤ ~10 rows (configurable):** the LLM interprets → `answer` (summary / stat /
  chart + trust trail).
- **Above the threshold:** **not** LLM-narrated → `table` result: columns + rows,
  **paginated** (e.g. 200/page). This is UX *and* governance — only small results
  reach the model.
- A `table` result offers two actions:
  - **Save as dataset** — materialize the **full** result (its own storage cap,
    separate from the display cap) to Parquet in the store, register + profile →
    it appears in the workbench, re-queryable and joinable. Fully local write, no
    egress.
  - **Download** — export the result (CSV/Parquet/Excel) as an artifact.

### Provenance (first-class)
A derived (saved) dataset carries **how it was made**: producing SQL/template,
source datasets (lineage), created-at. Feeds the product's lineage/trust story
and enables derivation chains (result → sources → their sources). Add a
`provenance` block to the catalog entry for derived datasets.

## 6. Phasing (by complexity)

| Phase | Scope | Runs | Machinery | Feature |
|---|---|---|---|---|
| 1 | Files only | Local DuckDB | done | **003** (shipped) |
| 2 | Within one DB | On that remote, read-only | route + result handling; **no** bindings | **007** |
| 3 | Files × one DB | Push file values, run remotely | full template/provider/always-remotely | **008** |
| — | Across DBs (DB×DB) | **not supported** | — | — |

**Across-DB is composed, not planned:** materialize DB-A's result as a
file/dataset (§5), then it's a file → Phase-3 handles files × DB-B. We never
build multi-remote query planning; users compose explicitly through derived
datasets — which is also more explainable (each step is a reviewable query + a
named intermediate table).

## 7. Where it lands
- **003 planner prompt/skill:** instruct the model to emit `sql_template` +
  `bindings` (provider query + `expand`) whenever a remote table is constrained
  by local data — **never inline data** — and to use the provider dataset's row
  count to stay under N.
- **Plan schema:** add `sql_template`, `bindings[]`, and the `table` vs `answer`
  result kind.
- **Runtime (007/008):** provider execution + cap(N) + dialect renderer +
  parameterized injection + read-only remote execution + narrate/tabulate switch
  + save-as-dataset + download.
- **006 workbench:** a "Results / Derived" grouping under Files; derived datasets
  show provenance in the detail pane.
- **Config:** `N` (default 100k), narrate-threshold (default ~10), display page
  size, storage cap.
