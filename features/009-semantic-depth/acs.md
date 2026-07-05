---
ac_count: 16
high_priority_count: 10
discovered: 2026-07-04
---

# Acceptance Criteria — Feature 009: Semantic depth

> Formalized from `feature.md` (four review threads) + the human's scoping
> decisions of 2026-07-04: **single-column** implied FKs; **cross-source**
> relationships included; DB-table cataloguing runs **automatically on connect,
> asynchronously, with progress + auto-refresh**. Domain-language,
> user-observable. Frontend flows bind to Playwright; discovery/validation bind
> to backend unit tests over synthetic + Chinook/Pagila data.

## Relationship discovery & validation

### AC-1: Declared keys are surfaced
Priority: High · Type: Functional
When a database is connected, each table's **declared** primary keys and foreign
keys (read from the database's own catalog) are captured and shown as
relationships on the affected tables.

### AC-2: Implied single-column foreign keys are discovered
Priority: High · Type: Functional
For data without declared foreign keys (files, or databases lacking them), the
system proposes **single-column** FK relationships by matching a column to a
candidate key (by name and compatible type) — e.g. `orders.customer_id` →
`customers.id`. Multi-column (composite) keys are out of scope for this feature.

### AC-3: A relationship is accepted only if referential integrity holds
Priority: High · Type: Functional
An inferred FK is accepted **only** when every **non-null** value of the child
column exists in the referenced key's value set (a true subset). If any non-null
value has no match, the relationship is **rejected** — it is never shown as a
valid FK. A column that merely shares a name but fails this check is not linked.

### AC-4: A nullable foreign key is an optional (outer-join) relationship
Priority: High · Type: Functional
If the child column contains nulls, the relationship is recorded as **optional**
(so a downstream join keeps unmatched rows — left/outer). A fully-populated child
column is a **required** (inner) relationship. The join type is part of the
recorded relationship.

### AC-5: Each relationship records its origin, evidence, and join type
Priority: Medium · Type: Functional
A relationship shows whether it is **declared** or **inferred**; for inferred
ones, the referential-integrity evidence (match coverage) and the join type
(required / optional) are recorded and viewable.

### AC-6: Cross-source relationships are discovered
Priority: Medium · Type: Functional
An implied FK may link a **file** column to a **connected-database** table (and
the reverse), validated by the same referential-integrity rule, computed locally.

### AC-7: Name-only matches that fail integrity are not linked
Priority: High · Type: Edge case
Two columns that share a name (e.g. unrelated `id` columns) but whose values
fail the referential-integrity subset check are left **unrelated** — no false
relationship is surfaced. Where a child column could plausibly reference more
than one table, the best integrity match is chosen (ties flagged for review),
not all of them.

## Richer meaning

### AC-8: Column meaning is derived from its name and its data
Priority: High · Type: Functional
Each column's plain-English description reflects its **name, sampled values,
type, and distribution** — a specific, data-grounded description, not a generic
placeholder like "Text column from the source table".

### AC-9: Table meaning aggregates its columns and relationships
Priority: High · Type: Functional
A table's description summarizes what the table represents, informed by its
columns **and** the relationships it participates in (e.g. "one row per order;
references customers and products").

## Real, automatic, async DB cataloguing

### AC-10: Connected-database tables are catalogued for real, automatically
Priority: High · Type: Functional
On connecting a database, its tables receive **real** (LLM-derived) semantic
descriptions — the same treatment files get — replacing the deterministic stub.

### AC-11: Cataloguing runs in the background with visible progress
Priority: High · Type: UX
Connecting a database **returns promptly**; each table shows a "cataloguing…"
progress indication and **refreshes to its real description when ready**, with no
manual reload. The workbench stays usable while cataloguing proceeds.

## Surface on focus

### AC-12: Focusing a table shows its meaning and relationships
Priority: High · Type: UX
Selecting a table shows its aggregated description and the relationships it
participates in — related-to links, each marked declared/inferred and
required/optional.

### AC-13: Focusing a column shows its meaning, role, and relationship
Priority: High · Type: UX
Selecting a column shows its derived description, its role, and any FK
relationship it carries (this column references table X; required/optional).

## Feed the planner

### AC-14: The planner joins on discovered relationships with the right join type
Priority: Medium · Type: Functional
When a question over loaded **files** needs a join, the generated SQL joins on a
**discovered relationship** using its recorded join type (required → inner,
optional → outer), and the semantic descriptions inform column selection —
visible in the answer's trust trail. (Q&A over connected databases arrives with
the federation phases; this AC covers the file case that already answers today.)

## Cross-cutting

### AC-15: Discovery preserves the governance invariant
Priority: High · Type: Constraint
Referential-integrity checks and distributions are computed **locally** in
DuckDB; relationship discovery sends only schema, profiles, and capped samples
to the LLM — never bulk data. Egress stays within the existing governance bound.

### AC-16: Relationships and descriptions survive a restart, and cataloguing failure is contained
Priority: Medium · Type: Cross-cutting
Discovered relationships and derived descriptions persist across a restart
(stored with the catalog). If the cataloguer fails or is unavailable for a
table, that table falls back to a clear not-yet-catalogued state without
breaking other tables or the workbench.
