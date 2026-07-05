---
ac_count: 11
high_priority_count: 7
discovered: 2026-07-05
---

# Acceptance Criteria — Feature 010: Workspace-aware cataloguing

> Formalized from `feature.md` + the human's scoping decisions of 2026-07-05:
> **deep context** (also the columns of directly-linked tables), **retroactive**
> re-cataloguing of affected tables, and **connected-DB catalog persistence**.
> Domain-language, user-observable. Discovery/cataloguing bind to unit tests over
> synthetic data; the LLM path via cassette, deterministic enrich offline.

## Cataloguing in the context of the workspace

### AC-1: A table is catalogued knowing the rest of the workspace
Priority: High · Type: Functional
When a table is catalogued (a file ingested, a query result saved, or a database
connected), the cataloguer is given a **workspace context**: the other tables'
names + descriptions, the columns of tables this one is directly related to, and
the relationship graph — not just the one table in isolation.

### AC-2: A table's meaning reflects its relationships
Priority: High · Type: Functional
The derived description and column roles reflect the workspace: a foreign-key
column is described in terms of the parent table it references (using that
parent's meaning), and the table description situates the table among the ones
it links to (e.g. "orders — one row per order, references the customers master").

### AC-3: Both cataloguing paths use the context
Priority: High · Type: Functional
The default offline (data-grounded, deterministic) cataloguer AND the opt-in LLM
cataloguer both receive and use the workspace context.

### AC-11: The context is available on a fresh session
Priority: Medium · Type: Functional
On a new session, the workspace context is built from the persisted/rehydrated
catalogs, so a table ingested in a fresh session is still grounded in the
existing workspace — no need to re-derive the whole workspace first.

## Keeping the workspace coherent (retroactive)

### AC-4: A new relationship re-catalogues the tables it affects
Priority: High · Type: Functional
When ingesting or connecting creates a relationship to existing tables, those
existing tables are re-catalogued so their meaning reflects the new link (an
existing "customers" learns it is now "referenced by orders").

### AC-5: Re-cataloguing is bounded to what changed
Priority: Medium · Type: Functional
Only the tables actually affected by the new relationship are re-catalogued —
never the whole workspace — so adding one table is not O(workspace).

## Persistence across sessions (connected databases)

### AC-6: A connected database's catalog persists
Priority: High · Type: Functional
A connected database's derived catalog (descriptions, roles, relationships) is
persisted, keyed by connection + table, alongside the file catalogs.

### AC-7: Reconnecting reuses the persisted meaning
Priority: High · Type: Functional
After a restart and reconnect, the database's tables show their previously
derived descriptions immediately, reusing the persisted catalog rather than
re-deriving it — unless the table's schema changed, in which case it is
re-catalogued.

## Cross-cutting

### AC-8: Only metadata crosses to the model
Priority: High · Type: Constraint
The workspace context contains only names, descriptions, roles, and
relationships — never bulk rows. Egress stays within the existing governance
bound (schema/profiles/capped samples/metadata only).

### AC-9: The offline path stays deterministic
Priority: Medium · Type: Constraint
The default offline cataloguer, with workspace context, remains deterministic —
stable output for stable input — so the query planner's prompt (and its
recorded cassettes) stay stable.

### AC-10: A cataloguing failure is contained
Priority: Medium · Type: Cross-cutting
If cataloguing or re-cataloguing a table fails, it degrades to the
table-in-isolation result (or the prior catalog) without breaking ingestion,
connect, or the other tables.
