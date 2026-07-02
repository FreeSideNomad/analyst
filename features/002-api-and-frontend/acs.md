---
ac_count: 11
high_priority_count: 6
discovered: 2026-07-02
---

# Acceptance Criteria — Feature 002: FastAPI layer & aligned frontend

> Derived from the approved Claude Desktop Design prototype (compressed
> discovery — the prototype's implemented behavior is the contract). AC-1..5
> are API-level; AC-6..10 are user-visible flows bound to Playwright e2e.

## API contract

### AC-1: Datasets are served over HTTP in domain-true wire shapes
Priority: High · Type: Functional
Listing datasets returns each dataset's envelope (id, name, file name, status,
row/column counts) with its full profile (inferred types, null rates, distinct
counts, samples, quantiles, mixed/nested facts) and catalog entry (table and
column descriptions, roles, clarifications) exactly mirroring the domain.

### AC-2: The real store is the default; fixtures are opt-in
Priority: High · Type: Functional
With no configuration, the API serves the real ingestion engine (DuckDB store).
Setting the fixtures flag serves the in-memory mock instead; the health endpoint
reports which mode is active.

### AC-3: A file can be ingested, tracked, refreshed, and deleted over HTTP
Priority: High · Type: Functional
Uploading a file creates dataset(s); ingestion status is observable per dataset;
a dataset can be refreshed (schema-validated, versioned per feature 001) and
deleted; deleting returns no content and the dataset disappears from listings.

### AC-4: Unknown datasets return a clear not-found error
Priority: Medium · Type: Error
Requesting or acting on a dataset that doesn't exist yields a 404 with a message
naming the dataset.

### AC-5: Provisional Q&A follows the clarify-then-answer contract
Priority: High · Type: Functional
Submitting an ambiguous question returns a clarification (question + concrete
options, the AskQuestion primitive); responding with a selection returns an
answer carrying a summary and a trust trail (assumptions, lineage, SQL).
Unambiguous questions answer directly. (Canned until the Q&A domain lands.)

## Frontend flows (e2e, mocked data)

### AC-6: The workspace renders the seeded datasets
Priority: High · Type: UX
Opening the app shows the workspace with the seeded datasets listed by name and
row count, hydrated from the API (fixtures mode).

### AC-7: A dataset's profile and catalog are revealable
Priority: High · Type: UX
Selecting a dataset reveals its profiling details (column types, null rates)
and its plain-English catalog descriptions — grab-the-wheel transparency.

### AC-8: Asking an ambiguous question surfaces a clarification the user can answer
Priority: High · Type: UX
Asking about revenue by region surfaces the clarification options; choosing one
produces the answer with its chart and expandable trust trail.

### AC-9: Uploading a file shows ingestion progressing to completion
Priority: Medium · Type: UX
Starting an ingest shows in-progress state and phases, reaches completion, and
the new dataset appears in the workspace.

### AC-10: The user can move between the ingestion and workspace views
Priority: Medium · Type: UX
The header navigation switches between the Ingestion view (upload + profiling
cards) and the Workspace view (datasets, catalog, Q&A); each renders its
content.

### AC-11: A dataset can be deleted from the UI
Priority: Medium · Type: UX
The workspace offers a delete affordance per dataset; deleting removes the
dataset from the visible list (and from the backend). (Added beyond the
prototype, which had no delete UI — human-requested 2026-07-02.)
