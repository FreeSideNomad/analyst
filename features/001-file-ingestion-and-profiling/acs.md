---
ac_count: 24
high_priority_count: 14
discovered: 2026-07-01
---

# Acceptance Criteria — Feature 001: File ingestion & agentic data profiling

> Checkpoint 2. Domain-language decisions about what must observably work. Given/When/Then formalization happens next (`atdd`).
> Feature scoped **workspace-light** (single default workspace, no auth). Storage/agent mechanics are implementation detail — these ACs describe observable behavior.

## Happy path

### AC-1: A clean delimited file becomes a queryable dataset
Priority: High · Type: Functional
Given a well-formed CSV with a header row, when a user ingests it, they get a named dataset whose columns and rows faithfully match the file, and the dataset can be queried and returns correct results.

### AC-2: Every column is profiled
Priority: High · Type: Functional
On ingestion, each column reports its inferred type, null rate, cardinality (distinct-value count), and representative sample values; numeric columns additionally report min/max and quantiles; the dataset reports its total row count.

### AC-3: The data is durably materialized and queryable
Priority: High · Type: Functional
Ingested data is stored in an efficient columnar form and is queryable after ingestion completes (and across restarts), returning results consistent with the source file.

### AC-4: An agent-authored semantic catalog entry is produced automatically
Priority: High · Type: Functional
Ingestion automatically produces a catalog entry containing a plain-English description of the table and of each column, plus an inferred role for each column, assembled without user intervention.

### AC-5: Rich scalar types are inferred
Priority: High · Type: Functional
Type inference distinguishes text, integer, decimal, boolean, date, and datetime; the inferred type is recorded per column.

### AC-6: Excel is supported, one dataset per non-empty sheet
Priority: High · Type: Functional
The full ingestion journey works for `.xlsx` files; each non-empty sheet becomes its own separately-profiled, separately-catalogued dataset.

### AC-7: TSV and JSON are supported
Priority: Medium · Type: Functional
Tab-separated files are ingested like CSV. JSON structured as an array of records becomes a dataset (one record → one row); JSON whose values are deeply nested is recorded as such in the profile rather than silently dropped.

### AC-8: A clean, unambiguous file ingests fully on autopilot
Priority: High · Type: UX
When a file is clean and unambiguous, the entire ingest→profile→catalog journey completes with no questions asked of the user.

## Edge cases

### AC-9: A mixed-type column is widened to text and recorded as mixed
Priority: High · Type: Edge
When a column's values do not resolve to a single type, it is typed as text (lossless), and the profile records that it was mixed, naming the dominant type and example off-type values. Ingestion does not stop.

### AC-10: A headerless file gets synthesized column names
Priority: Medium · Type: Edge
The system detects whether the first row is a header; if the file is headerless, it synthesizes column names (e.g. column_1…column_n) without consuming a data row, and records that names were synthesized.

### AC-11: Header-only vs truly-empty files
Priority: Medium · Type: Edge
A file with headers but no data rows becomes a valid zero-row dataset with a fully profiled schema. A file with no columns/no content produces a clear, friendly error.

### AC-12: Duplicate column names are auto-disambiguated
Priority: Medium · Type: Edge
When the source has duplicate column names, they are automatically made unique (e.g. name, name_2) so the dataset is queryable, and the original duplication is recorded in the profile.

## Errors & security

### AC-13: Non-UTF-8 encodings are auto-detected and decoded
Priority: Medium · Type: Error
Files in common non-UTF-8 encodings (UTF-16, byte-order-marked, latin-1) are detected and decoded correctly; the detected encoding is recorded in the profile.

### AC-14: Unsupported formats are rejected clearly
Priority: Medium · Type: Error
A file whose format is not supported (e.g. .parquet, .pdf) is rejected with a clear message that names the supported formats (CSV, TSV, Excel, JSON). Nothing is partially ingested.

### AC-15: Malformed or corrupt files fail cleanly
Priority: High · Type: Error
A file that cannot be parsed produces a clear, actionable error and leaves no partial dataset behind.

### AC-16: Governance invariant — no bulk data leaves the box
Priority: High · Type: Security
Only schema, profiles, and a capped number of small samples are ever sent to the AI model; the amount of sample data is bounded by an enforced cap. Every model interaction's payload is recorded in an egress log, and it is verifiable that no bulk row data ever appears in that log.

### AC-17: Ingestion is all-or-nothing
Priority: High · Type: Error
If profiling or cataloguing fails partway through, no half-created dataset remains; the user sees a clear error and can retry cleanly.

## Cross-cutting

### AC-18: Refresh reloads data into an existing schema, validated before replacement
Priority: High · Type: Functional
A user can refresh an existing dataset by loading new data into its established schema. Before the existing data is replaced, the new data is validated for conformance to that schema/profile. If it conforms, the data is replaced. If it does not, the system does not silently proceed — it surfaces the conflicts via a structured question (the AskQuestion primitive) and lets the user choose to loosen the validations (relax the schema/constraints) before proceeding.

### AC-19: Refreshes are versioned and non-destructive
Priority: Medium · Type: Cross-cutting
A refresh creates a new version of the dataset; the prior version is retained and the catalog links versions so the change is traceable.

### AC-20: A dataset can be deleted cleanly
Priority: Medium · Type: Lifecycle
A user can delete a dataset; deletion removes its materialized data and its catalog entry completely, leaving no orphaned artifacts.

### AC-21: Performance envelope is bounded and honest
Priority: Medium · Type: Performance
Files up to roughly 1 GB / a few million rows are profiled and catalogued responsively. A file beyond the supported envelope produces a clear "too large for this version" message rather than hanging or failing obscurely.

### AC-22: The agent asks rather than guesses when confidence is very low
Priority: Medium · Type: UX
When the agent genuinely cannot confidently describe or assign a role to a column, it emits a structured AskQuestion (a question with concrete options) rather than fabricating a description — the only interactive path in an otherwise autopilot ingestion.

### AC-23: Ingestion status is observable
Priority: Medium · Type: Cross-cutting
The state of an ingestion (in progress, complete, failed) and the completeness of profiling are observable, so a user can tell whether a dataset is ready and trustworthy.

### AC-24: Profiling is validated against a real-world golden corpus
Priority: High · Type: Validation
Profiling and type-inference correctness are validated against a curated golden set of real-world datasets (sourced from Kaggle and other public data) with known ground truth — not only synthetic fixtures — so behavior on messy real data is measured, not assumed. The curated corpus and feature-001 starter set are in `docs/golden-corpus.md`; those datasets seed the ATDD acceptance fixtures.

---

## Coverage summary

- **Happy path:** AC-1…AC-8 ✅
- **Edge cases:** AC-9…AC-12 ✅
- **Errors & security:** AC-13…AC-17 ✅ (governance invariant AC-16 is the security-critical one)
- **Cross-cutting:** AC-18…AC-24 ✅
- **Domain checklists:** no matching written checklist for this surface (auth deferred; `data-migration.md` — which would fit AC-18's refresh flow — is not yet written).

## Notes / flags for downstream

- **AC-18 (refresh-with-validation-and-loosening)** is a meaty sub-capability and the main interactive path in 001. If it proves too large at `plan` time, it is the natural split point (feature 001a).
- **AC-24** depends on the golden-corpus curation task (research in progress). The corpus will seed the ATDD acceptance fixtures.
- The AskQuestion primitive is exercised by AC-18 and AC-22 — 001 builds *and* uses it, not just stubs it.
