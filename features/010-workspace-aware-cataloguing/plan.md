---
slug: workspace-aware-cataloguing
checkpoint: 4
plan_status: approved
created: 2026-07-05
---

# Plan — Feature 010: Workspace-aware cataloguing

> Checkpoint 4. Human pre-approved autonomous CP4+CP5 at spec approval
> (2026-07-05), so the architecture below is confirmed by that delegation.

## Architecture

### The core object: `WorkspaceContext` (domain)

New in `src/analyst/domain/workspace.py`:

- `TableContext(name, description, columns: tuple[ColumnDescription,...])` —
  one already-catalogued sibling table. `columns` is populated **only for
  tables directly related to the table being catalogued** (the approved "deep
  context" scoping); unrelated tables carry name + description only.
- `WorkspaceContext(tables: tuple[TableContext,...], relationships:
  tuple[Relationship,...])` with a `for_table(name)` view that trims sibling
  columns to direct links. Metadata-only **by construction** (names,
  descriptions, roles, relationships — the type cannot hold rows), which is how
  AC-8 is satisfied structurally rather than by policing call sites.
- `build_workspace_context(catalogs: Mapping[str, CatalogEntry|None],
  relationships) -> WorkspaceContext` — pure function, deterministic (sorted
  iteration).

### Where the context is built and how it flows

Catalogs live at the **repository layer** (`StoreRepository._records` +
sidecars; `DatabaseManager` for connected tables). The service and manager get
a *source of catalogs*, not a pre-built context:

1. **File path** — `IngestionService` gains an optional
   `catalog_source: Callable[[], Mapping[str, CatalogEntry|None]]`.
   `StoreRepository` passes `lambda: {name: record.summary.catalog}` (which
   includes federated records — file and DB siblings both contribute).
   `IngestionService._catalog` builds the context next to where it already
   discovers relationships, then calls:
   - `enrich.catalog_entry(dataset, profile, rels, context=ctx)` (default), or
   - `self.cataloguer.catalog(payload, rels, context=ctx)` (opt-in LLM).
   A bare `IngestionService(store)` (feature-001 acceptance seam) has no
   source → empty context → **byte-identical output to today** (the
   determinism/compat rule below).
2. **DB-connect path** — `DatabaseManager.connect` builds one context from
   `self.repo` records and passes it through `CatalogFn`, whose signature
   grows to `(table, relationships, context)`.
3. **Fresh session (AC-11)** — no new machinery: `StoreRepository._rehydrate`
   already reloads catalogs from sidecars into `_records`, and the
   `catalog_source` reads `_records`.

### Weaving context into meaning (enrich + LLM prompt)

- `enrich._column_description` FK branch: when the context knows the parent
  table, append the parent's meaning — e.g.
  `Foreign key: each customer_id references customers.id (required) —
  customers: <first sentence of the parent's description>`.
- `enrich._table_description`: situate among linked tables — after
  `References customers (via customer_id).` append the parent's short meaning;
  `Referenced by orders.` gains the child's short meaning.
- `cataloguer.render_prompt` gains a `Workspace context:` section (sibling
  names + descriptions; columns for directly-linked tables; relationship
  lines). **Emitted only when the context is non-empty**, so every existing
  single-table cassette key is unchanged.

**Determinism/compat rule (AC-9):** empty context ⇒ output identical to
today; non-empty context ⇒ still a pure function of (profile, relationships,
context), all iteration sorted. Cassette consequence: only multi-table
fixtures churn — re-record `join_planner.json` (orders+customers) and any
planner key whose prompt now carries context-enriched descriptions; record a
new cataloguer cassette for the LLM-path acceptance scenario.

### Retroactive re-cataloguing (slice 2)

After `StoreRepository.ingest` (and `DatabaseManager.connect`) lands new
tables, compute the **affected set**: existing tables that appear in a
relationship whose other side is a new table. For each affected record only —
never the whole workspace (AC-5) — re-derive its catalog through the same
path that catalogued it category-wise (configured cataloguer if present, else
enrich), using `record.summary.profile` + fresh relationships + fresh context;
update the record and its sidecar. Each re-derivation is wrapped: a failure
keeps the prior entry and never fails the ingest/connect (AC-10). A failure
building the context itself degrades the *new* table to
cataloguing-in-isolation (AC-10, second scenario).

### Connected-DB catalog persistence (slice 3)

Reuse the existing sidecar mechanism — federated records are named
`<connection>.<table>`, so `<connection>.<table>.catalog.json` is already
keyed by connection + table (AC-6):

- `DatabaseManager._apply` persists the entry via a repository hook
  (`StoreRepository` writes the sidecar; `FixtureRepository` no-op).
- Sidecar JSON gains a top-level `schema_fingerprint` (sorted column
  name:type pairs) — existing loaders ignore unknown keys, existing sidecars
  simply have no fingerprint (treated as "must re-derive"), so the change is
  backward compatible.
- `DatabaseManager.connect`: per table, if a sidecar exists **and** its
  fingerprint matches the freshly profiled schema → the record is created
  with the persisted catalog, `catalog_status="complete"`, no background job
  (AC-7 reuse); otherwise the normal pending → background path runs (AC-7
  schema-changed branch).

### Coupling / blast radius

- `enrich.catalog_entry`, `Cataloguer.catalog`, `CatalogFn` grow an optional
  trailing `context` parameter (default empty) — all existing call sites and
  tests compile unchanged.
- `IngestionService.__init__` grows optional `catalog_source`; `ingest()`
  signature unchanged (feature-001 board untouched).
- No wire-schema change; the frontend is untouched. Egress governance: the
  context adds *descriptions of sibling tables* to the LLM prompt — still
  within the schema/profiles/metadata bound (AC-8); the egress payload type
  gains nothing row-shaped.

### Alternatives considered

- *Build context inside `DatasetStore`* — rejected: the store owns data, not
  meaning; catalogs live above it.
- *Pass a pre-built `WorkspaceContext` into `service.ingest()`* — rejected:
  it would go stale between multi-sheet Excel datasets in one ingest and
  forces every caller to know how to build it; a callable source stays fresh.
- *Persist DB catalogs in a new registry file* — rejected: the per-dataset
  sidecar already keys by `connection.table` and survives restarts; one
  mechanism, not two.

## Charter Check

| Charter rule | Status | Note |
|---|---|---|
| Layered architecture (domain ← engine ← service ← api) | ✅ | `WorkspaceContext` in domain; building in service/repository; no upward imports. |
| Governance: raw bulk data never leaves the box | ✅ | Context is metadata-only by type construction (AC-8); prompt gains descriptions only. |
| Acceptance pipeline: spec.md → IR → generated tests; never hand-edit generated | ✅ | 18-scenario board generated via `acceptance.ctx010`; slices bind steps. |
| TDD, unit + acceptance both green before merge | ✅ | Each slice: failing acceptance steps → unit-driven implementation → green. |
| Determinism of offline/cassette paths | ✅ | Empty-context byte-compat rule; sorted iteration; cassette re-record once. |
| Autonomy stance (high) + explicit validation method | ✅ | Human pre-approved CP4+CP5; validation per feature.md (unit + cassette + live-marked test + boards green). |

No deviations → no amendment ADRs.

## Phasing

1. **Slice 1 — context cataloguing** (AC-1, 2, 3, 8, 9, 11): domain object +
   builder; service/manager threading; enrich weaving; prompt section;
   cassette re-records; bind scenarios 1–7, 14, 15.
2. **Slice 2 — retroactive** (AC-4, 5, 10): affected-set computation; bounded
   re-derivation at repository/manager; failure containment; bind scenarios
   8–10, 16–18.
3. **Slice 3 — DB persistence** (AC-6, 7): sidecar persistence hook +
   fingerprint; reconnect reuse; bind scenarios 11–13.

## Performance budgets

- Context build is O(tables) dict/tuple assembly per ingest — negligible next
  to profiling; no extra SQL.
- Retroactive re-cataloguing bounded to affected tables (AC-5) and offline by
  default (enrich, microseconds/table). LLM-path retroactive cost = one call
  per affected table — acceptable at workspace scale (tens of tables).
- Reconnect with persisted catalogs skips the background pool entirely —
  strictly faster than today.

## Test strategy

Per `feature.md.validation_method`: unit tests over the `WorkspaceContext`
builder + cataloguing-with-context (deterministic enrich path + LLM path via
cassette); a **live-marked** test showing a table catalogued in context
references a related table's meaning; existing boards stay green.

- Unit: `tests/unit/test_workspace_context.py` (builder: trimming, sorting,
  determinism, metadata-only), enrich-with-context, prompt-with-context,
  retroactive affected-set, fingerprint match/mismatch.
- Acceptance: the 18-scenario board via `acceptance.ctx010` (in-process:
  `StoreRepository` + `DatabaseManager` + synthetic SQLite; LLM scenario via
  cassette).
- Live-marked: record the context cataloguer cassette; retry loop per the
  established recorder pattern.
- Full-suite gate before PR: `./run-acceptance-tests.sh` (all features) +
  `uv run pytest` + pre-commit hooks.

## Collaboration schedule / execution modes

Single local agent, autonomous through CP5 (human delegation recorded at spec
approval); human returns at PR review. Live cassette re-records run locally
(subscription auth).
