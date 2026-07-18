---
slug: catalog-curation
checkpoint: 4
plan_status: approved  # blanket in-session delegation (owner AFK 8h, "assume everything approved")
created: 2026-07-18
---

# Plan — 016 catalog curation

## Architecture

**Grounding facts:** clarifications already travel on
`CatalogEntry.clarifications` (domain) and render in the workbench;
catalogs persist as per-dataset sidecars and are re-derived by refresh /
retroactive re-cataloguing (010); the cataloguer speaks through
`LLMGateway` with record/replay cassettes in `tests/cassettes/`; the Q&A
planner reads catalog descriptions via `query_table_from_summary`. The
fixtures workspace seeds one clarification on `transactions.merchant`.

### Components

1. **Curation state — a per-dataset sidecar** `<name>.curation.json`
   (exact 013-decisions pattern): `{columns: {col: {kind: answer|
   correction, input, description, confirmed_at?, pending_reconciliation}},
   table: {...}}`. The `CatalogEntry` itself stays untouched as a domain
   shape — curation is an OVERLAY the repository applies wherever catalog
   entries are (re)derived: `_apply_curation(name, entry)` replaces the
   curated column/table descriptions and strips answered clarifications.
   Called at `_rehydrate`, after `refresh`, and after
   `recatalogue_affected` — that single choke point IS the stickiness
   guarantee (AC-6).

2. **Agent synthesis — `src/analyst/agentic/curation.py`** (versioned
   prompt, structured output): given the column's profile facts, current
   descriptions, the clarification question (if any), and the user's
   answer/correction as GROUND TRUTH, return
   `{column_description?, table_description?}` — at most those two fields
   by construction (AC-4's blast radius enforced by the output schema, not
   by hope). Speaks through `LLMGateway`: live backend in the app,
   `ReplayBackend` cassette (`tests/cassettes/curation.json`, recorded
   once live) in the board. No cataloguer configured → offline path.

3. **Repository (`StoreRepository`)**:
   - `curation(name)` → open clarifications + curated-state map (badges).
   - `answer_clarification(name, column, answer)` — locate the
     clarification (unknown → `UnknownCurationError`); empty answer →
     `ValueError`; synthesize (or offline-template); update the catalog
     entry via the overlay; persist catalog + curation sidecars. Agent
     failure → nothing persisted, error surfaced (AC-12).
   - `suggest_correction(name, column_or_none, note)` — same pipeline;
     `column_or_none=None` targets the table description.
   - Offline template: description = the user's words (correction) or
     `"<question> — settled by the user: <answer>"` (clarification),
     `pending_reconciliation: true`.
   - `FixtureRepository`: seeded merchant clarification becomes
     answerable in memory (templated completion) so the browser flows run.

4. **API — extend `routes/datasets.py`**:
   `GET /api/datasets/{name}/curation`,
   `POST /api/datasets/{name}/curation/answer` `{column, answer}`,
   `POST /api/datasets/{name}/curation/correct` `{column?, note}`.
   404 unknown clarification/dataset, 400 empty input, 502 failed
   synthesis (catalog untouched). Camel schemas.

5. **Frontend (`IngestionPage`)**: the Needs-review card becomes a form —
   radio options + "Something else" text input + submit; column drilldown
   and table description get "Suggest a correction" (small textarea +
   submit); curated columns/table show a `human-confirmed` Badge
   (tone=success). State updates in place from the POST response — no
   reload (AC-10).

6. **Planner effect (AC-9)** — no new code: `query_table_from_summary`
   already joins catalog descriptions into the planner's view; the board
   pins that the settled text is present in that view.

### Key decisions

- **Overlay, not domain mutation** — curation survives every re-derivation
  path through one function; the domain and wire shapes stay stable.
- **Blast radius enforced structurally** — the synthesis output schema has
  exactly two optional fields; there is nothing else it *can* touch.
- **One pipeline for answers and corrections** — same sidecar, same
  prompt family, same badge; the UI difference is just the entry point.
- **Cassette-first determinism** — the board never calls a live model; the
  curation cassette is recorded once by script (like 010's).

## Charter Check

| Charter rule | Status | Evidence |
|---|---|---|
| Domain core pure | ✅ | curation state is repository-layer; domain untouched except (nothing) |
| DuckDB only via engine | ✅ | no new SQL |
| Agentic prompts versioned, structured outputs | ✅ | `agentic/curation.py` prompt + output schema in-tree; cassette-recordable |
| Human-curatable catalog | ✅ | this feature IS that promise |
| Never silently applied / overwritten | ✅ | stickiness overlay + AC-6 gate; agent failure leaves catalog untouched |
| Governance: metadata only to the model | ✅ | prompt carries profile facts + catalog text + the user's answer; never rows |
| API thin | ✅ | routes delegate; schemas map |
| Autonomy | high (blanket delegation), matched by validation_method (stickiness + blast-radius mutation gates, cassette board, browser e2e) |
| Mutation policy | gates: (1) drop overlay on re-catalogue → AC-6 red; (2) let synthesis write another table's entry → AC-4 red; (3) persist on failed synthesis → AC-12 red |

**Amendments:** none.

## Phasing

1. Curation sidecar + offline path + overlay + stickiness (unit-first);
   bind AC-1/5/6/8 scenarios (offline template).
2. Agent synthesis module + cassette recording script + live path; bind
   AC-2/3/4/7/9/12 scenarios (replay).
3. API routes + fixture parity; route unit tests.
4. Workbench form + correction affordance + badges; browser scenarios;
   board 14/14.
5. Harden: the three mutation gates, full sweep, docs.

## Performance budgets

Curation ops: one model call (live) or none (offline/replay) + two sidecar
writes + one catalog-entry rewrite — interactive latency dominated by the
model call, seconds. Zero cost to datasets never curated.

## Collaboration schedule / Execution modes

Autonomous (blanket delegation); handoffs per checkpoint; PR at the end;
then feature 015 begins.

## Test strategy

Board: 12 in-process + 2 browser scenarios; agent turns replay
`tests/cassettes/curation.json`. Units: sidecar round-trip, overlay
application at each re-derivation path, offline templates, output-schema
bounds, route codes. Mutation gates as listed. Browser e2e over the seeded
`transactions.merchant` clarification and a `sales.billing_region`
correction.
