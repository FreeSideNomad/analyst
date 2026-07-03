---
ac_count: 10
high_priority_count: 7
discovered: 2026-07-03
---

# Acceptance Criteria — Feature 003: Natural-language Q&A over a dataset

> The real Q&A brain replaces the canned feature-002 stand-in. A user asks a
> plain-English question about the loaded datasets and gets a confidence-gated
> response: a direct answer when confident, a structured AskQuestion
> clarification when ambiguous, an abstention when out-of-scope. Every answer
> carries the trust trail (assumptions, lineage, SQL). The wire contract
> (CONTRACT.md Q&A shapes) does not change — the frontend already speaks it.
>
> Real-planner ACs (AC-1..AC-5) bind over HTTP against a service running the
> real planner with recorded-real model responses (deterministic replay);
> fixtures-mode ACs bind against the retained canned path. UI flows bind via
> Playwright against the fixtures API.

## API contract

### AC-1: A confident question is answered directly with a trust trail
Priority: High · Type: Functional
With a dataset ingested, asking an unambiguous aggregate question returns a
direct answer: the planner targets the semantic catalog metadata, generates
SQL, the SQL executes locally in DuckDB, and the answer's summary reflects the
locally computed value. The trust trail carries the planner's assumptions, the
data lineage, and the exact SQL that was executed.

### AC-2: An ambiguous question yields a structured AskQuestion clarification
Priority: High · Type: Functional
When a question has multiple plausible interpretations (e.g. two candidate
region columns), the planner does not guess: it returns a structured
clarification — a question plus concrete labelled options — instead of an
answer.

### AC-3: Answering the clarification completes the query
Priority: High · Type: Functional
Responding to a pending clarification with a selected option re-plans with
that choice and returns a direct answer with a trust trail whose SQL uses the
chosen interpretation.

### AC-4: Out-of-scope questions abstain rather than fabricate
Priority: High · Type: Functional
A question that cannot be answered from the loaded datasets (out-of-domain)
returns an abstention: the answer is flagged as abstained, explains that the
question is outside the catalog, and fabricates no chart, no figures and no
SQL.

### AC-5: Only validated SELECT SQL ever executes
Priority: High · Type: Governance
Generated SQL is validated before execution: it must be a single SELECT (or
WITH…SELECT) statement, reference only datasets and columns that exist in the
catalog, and contain no data-modifying or environment-touching statements. A
plan that fails validation is never executed — the service abstains and the
response carries no SQL.

### AC-6: The health endpoint reports which Q&A engine is serving
Priority: Medium · Type: Functional
The service health reports the Q&A mode: "real" when the real planner serves
(default), "canned" when the deterministic fixtures path serves.

### AC-7: Fixtures mode keeps the deterministic Q&A contract
Priority: High · Type: Functional
With fixtures enabled, the Q&A endpoints keep the deterministic, LLM-free
behavior on the unchanged wire contract: an ambiguous question returns a
clarification whose response yields an answer with a trust trail, an
unambiguous question answers directly, and an out-of-scope question abstains.

## Frontend flows (e2e, mocked data)

### AC-8: An out-of-scope question visibly abstains in the chat
Priority: High · Type: UX
Asking a question the workspace cannot answer shows an abstention message in
the chat that names what the workspace does cover, with no chart and no trust
trail — the user sees the agent declining, not a fabricated answer.

### AC-9: A confident question renders a stat answer with its trust trail
Priority: Medium · Type: UX
Asking an unambiguous single-value question renders a stat-block answer with
the computed value, and the trust trail is expandable down to the exact SQL.

### AC-10: An aggregate answer renders as a chart with its leader highlighted
Priority: Medium · Type: UX
Asking a top-N aggregate question renders a bar-chart answer with the leading
entity visible, and the trust trail's SQL reveals the join that produced it.
