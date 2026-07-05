---
ac_count: 5
high_priority_count: 4
discovered: 2026-07-05
---

# Acceptance Criteria — Feature 007: within-DB Q&A (phase 2)

> First increment (full autonomy): the execution core — a connected scanner
> database's tables become **queryable** in the store's connection, are offered
> to the planner (with discovered relationships), and planner SQL runs against
> the source read-only. Result-table view + live-DB e2e are follow-ons.

### AC-1: A connected scanner database's tables become queryable
Priority: High · Type: Functional
Connecting a SQLite or PostgreSQL database registers each of its tables in the
analytical store so SQL can run against them (scanner push-down, read-only). The
tables are marked queryable in the catalog (no longer "not yet answerable").

### AC-2: The planner answers over connected-database tables
Priority: High · Type: Functional
A connected database's tables are included in the planner's table set, so a
plain-English question about them produces runnable SQL — not an abstain about
un-runnable tables.

### AC-3: Generated SQL executes against the source
Priority: High · Type: Functional
Validated planner SQL over a connected table runs in the store's connection and
returns a small, capped result — including a join across two connected tables on
a discovered relationship.

### AC-4: Disconnecting removes queryability
Priority: High · Type: Functional
Detaching a database drops its queryable views; its tables are no longer
runnable and no longer appear to the planner.

### AC-5: Bulk data stays at the source
Priority: Medium · Type: Constraint
Only schema, profiles, capped samples, and small result sets cross the boundary;
the connection is read-only and query execution pushes down to the remote — no
bulk copy into the box.
