---
ac_count: 12
high_priority_count: 8
discovered: 2026-07-04
---

# Acceptance Criteria — Feature 006: two-surface workbench UX

> Formalized from the confirmed requirements in `feature.md` (decisions of
> 2026-07-04). Domain-language, user-observable. AC-12 is the one open decision
> flagged for the human. Frontend flows bind to Playwright; the naming change
> binds to backend unit tests.

## The workbench (Ingest & Profile)

### AC-1: Data is added from one place — files and databases
Priority: High · Type: Functional
On Ingest & Profile the user can both **upload a file** and **connect a
database** (engine, host/port/database/user/password, or a SQLite file path).
Database connection management (connect / list / disconnect) lives here, not on
the Query surface.

### AC-2: Everything added is browsable as a source-grouped tree
Priority: High · Type: UX
The left rail has two sections — **Files** and **Databases** — each grouping its
sources by the first name segment, expandable to their tables, and each table
expandable to its columns.

### AC-3: Datasets are named consistently by source
Priority: High · Type: Functional
Ingested data is named `source.entity.ext` and grouped by the first segment:
an Excel sheet → `<file>.<sheet>.xlsx`; a single-table file (CSV/TSV/JSON) →
`<file>.<ext>` shown as a group of one; a database table → `<connection>.<table>`.

### AC-4: A selected table reveals its profile
Priority: High · Type: UX
Selecting a table shows its profiling — per-column inferred type, null rate,
distinct count, samples, and numeric ranges — for files and database tables
alike.

### AC-5: A selected table reveals its semantic catalog
Priority: High · Type: UX
The same detail view shows the plain-English catalog — the table description and,
per column, its description and role — and surfaces any "needs review"
clarifications. (The metadata currently on the Query view lives here now.)

### AC-6: A column can be drilled into
Priority: High · Type: UX
Selecting a column shows a drilldown combining its full profile (stats,
distribution, samples) with its semantic description and role.

### AC-7: Connected-database tables are shown but marked not-yet-queryable
Priority: Medium · Type: UX
Tables from a connected database appear in the Databases section, profiled and
catalogued, but are clearly indicated as not yet answerable by Q&A (that arrives
with the phased federation features). The user is never left with a broken query.

### AC-8: A database can be disconnected
Priority: Medium · Type: Functional
Disconnecting a database removes its group and tables from the workbench; its
connection secret is never shown.

## The Query surface

### AC-9: The Query tab is the conversation only
Priority: High · Type: UX
The tab is named **Query** (not "Catalog & Q&A") and shows only the chat — no
catalog tree, no metadata pane, no column drilldown.

### AC-10: Asking a question still answers over the loaded files
Priority: High · Type: Functional
Q&A over uploaded files works exactly as before (confidence-gated answer /
clarification / abstain, with the trust trail); the restructure changes only
where metadata is browsed, not the answering.

## Cross-cutting

### AC-11: Moving between the two surfaces is preserved
Priority: Medium · Type: UX
The header navigation switches between Ingest & Profile and Query; each renders
its content and the app never loses the current workspace context.

### AC-12: The catalog is display-only in this feature
Priority: Medium · Type: Constraint
The semantic catalog is shown richly but is **read-only** here. Editing it
("grab the wheel" — correcting descriptions/roles, chat-to-curate) is a
separate later feature. Decided by the human 2026-07-04.
