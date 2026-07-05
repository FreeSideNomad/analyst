---
slug: workspace-aware-cataloguing
title: Workspace-aware cataloguing — derive a table's meaning in the context of the whole workspace
outcome: When a table is catalogued (a file ingested, a result saved, a database connected), its meaning is derived KNOWING the rest of the workspace — the other tables' names + descriptions and the relationship graph — instead of in isolation. So a new "orders" table is understood in light of the "customers" it references. The workspace's semantic context is loaded once and reused; it survives a session (persisted + rehydrated) for files today, and this feature extends that to connected databases. Only metadata (names, descriptions, relationships) ever crosses to the model — never bulk rows.
status: ready
autonomy_level: high
assignee: local
owner: igormusic
area: agentic
tracker_ref: local://workspace-aware-cataloguing
branch: workspace-aware-cataloguing
validation_method: "Unit tests over the WorkspaceContext builder + cataloguing-with-context (deterministic enrich path + LLM path via cassette); a live-marked test showing a table catalogued in context references a related table's meaning; existing boards stay green."
size: M
created: 2026-07-05
---

# Feature 010 — Workspace-aware cataloguing

> From the design discussion of 2026-07-05. Today cataloguing is PER-TABLE:
> `enrich.catalog_entry(table, profile, relationships)` / `Cataloguer.catalog(one
> payload)` see only the one table + relationship *names* — never sibling
> tables' meanings. Queries already get full context (catalogs persist in
> sidecars and rehydrate); *cataloguing* does not. This closes that gap.

## The problem (grounded in code)
- `IngestionService._catalog` and the connect path catalogue one table at a
  time; the payload carries that table's schema + samples only.
- Cross-table signal is limited to discovered relationships (name-level FK links).
- File catalogs persist + rehydrate (`_save/_load_catalog_sidecar`), so **queries**
  have full context on session resume. Connected-DB catalogs do **not** persist.

## Scope (to be pinned by the AC pass)
- A **WorkspaceContext** (existing tables' names + short descriptions + the
  relationship graph) fed into cataloguing, for both new-table ingestion and
  database connect, and to both the offline `enrich` path (default) and the LLM
  `Cataloguer` (opt-in).
- Governance bound: only metadata crosses (names/descriptions/relationships),
  never bulk rows.

## Open scoping decisions (resolve in discover-acs)
- Context depth: table-level only, or also related columns?
- Retroactive re-cataloguing of existing tables when a new relationship appears?
- Persist connected-DB catalogs across sessions (in this feature or later)?
