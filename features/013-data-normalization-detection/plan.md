---
slug: data-normalization-detection
checkpoint: 4
plan_status: approved  # in-session full-autonomy delegation (owner AFK), post-hoc review expected
created: 2026-07-15
---

# Plan — 013 data normalization detection

## Architecture

**The load-bearing fact (from `engine/store.py`):** every file dataset is a
DuckDB VIEW named `<dataset>` over the latest versioned Parquet
(`_register_parquet` → `CREATE OR REPLACE VIEW … AS SELECT * FROM
read_parquet(vN)`), and *everything* downstream — profiling
(`profile_relation(con, dataset)`), NL Q&A SQL, fetch/export — reads that
view. Normalization therefore needs exactly one mechanism: **rewrite the
view's SELECT with an explicit value mapping; never touch the Parquet.**
Approve = view carries CASE mappings; revoke = plain view again; the raw
file bytes and all Parquet versions stay intact (AC-7). Profiles and Q&A
inherit the standardized values with zero extra plumbing (AC-6, AC-9).

### Components

1. **Domain — `src/analyst/domain/normalization.py`** (pure, no I/O):
   - `Variant(value, rows)`, `VariantGroup(canonical, variants)` — evidence.
   - `NormalizationRule(rule_id, column, groups, mapping, description)` —
     `rule_id` is deterministic (`norm:<column>`, one rule per column in
     v1), `mapping` is the explicit raw→canonical dict, `description` is
     the rendered plain-language sentence (AC-4).
   - Canonicalization policy (pure functions): key =
     `casefold(collapse_ws(trim(v)))`; canonical = most frequent variant,
     ties → the variant matching its own title-case if present, else the
     lexicographically smallest. Deterministic for a fixed input.

2. **Engine — `src/analyst/engine/normalization.py`** (owns the DuckDB
   reads, via the store's connection):
   - `detect(con, dataset, profile) -> tuple[NormalizationRule, ...]`.
     Candidate columns from the existing profile: text-typed, >1 distinct,
     `distinct/rows ≤ 0.5` **and** `distinct ≤ 200` (identifier exemption,
     AC-12, and a hard cost cap). One `GROUP BY` per candidate; group by
     canonical key; groups with ≥2 raw variants become a rule.
   - **`DatasetStore` gains** `apply_normalization(dataset, mapping)` /
     `clear_normalization(dataset)` — recreate the dataset view over the
     latest Parquet with/without per-column CASE expressions, and
     `normalized_columns(dataset)` for introspection. All SQL stays in the
     engine layer (charter).

3. **Repository — `StoreRepository`** (orchestration + persistence):
   - `normalization(name)` → pending proposals (detection minus dismissed
     minus already-approved columns) + applied rules.
   - `approve/dismiss/revoke_normalization(name, rule_id)`; unknown id →
     `UnknownNormalizationError` (→ clean 404, folded error AC).
   - Decisions persist in a per-dataset sidecar
     `<dataset>.normalization.json` (exact pattern of the 010 catalog
     sidecars): `{column: {status, mapping, description}}`. `_rehydrate`
     re-asserts approved views on boot (AC-10); `refresh()` re-applies them
     after the view is recreated (new file versions keep the standard).
     Approve/revoke re-profile the dataset record so `profile` tells the
     truth (AC-9).
   - `FixtureRepository`: seeded proposal on the sample `sales.region`
     column with case variants; approve/dismiss mutate fixture state — this
     is what the browser scenarios drive.

4. **API — extend `routes/datasets.py`** (the dataset surface):
   - `GET /api/datasets/{name}/normalization` → `{proposals, applied}`.
   - `POST /api/datasets/{name}/normalization/{rule_id}/(approve|dismiss|revoke)`.
   - Camel-cased schemas in `api/schemas.py`; `UnknownNormalizationError`
     mapped to 404 alongside the existing domain-error handlers.

5. **Frontend — `IngestionPage`** (+ `api/client.ts`, `api/types.ts`):
   - Column row shows an amber "proposal" indicator when pending rules
     exist for the dataset (AC-11's pre-open pin).
   - The column drilldown renders each proposal: description + variant
     table (value, rows) + Approve / Dismiss; applied rules show Revoke.
     Local state update on action — no reload.

### Key decisions

- **View overlay, not data rewrite** — the only design that satisfies AC-7
  (reversible, original recoverable) without copying data. Alternative
  (normalized Parquet copy) rejected: doubles storage, breaks version
  semantics, revoke becomes a rebuild.
- **Explicit stored mapping, not a SQL normalize function** — the approved
  rule is a frozen value map; new variants arriving later do NOT silently
  fold in (they surface as a new proposal on re-detection). Honors "never
  silently applied" across time, and makes the trust trail exact.
- **Detection on demand** (GET), decisions persisted — ingest latency
  unchanged; nothing runs unless someone looks.
- **One rule per column (v1)** — keeps ids deterministic and the UI honest;
  multi-rule composition is a later slice if ever needed.

## Charter Check

| Charter rule | Status | Evidence |
|---|---|---|
| Domain core imports nothing outward | ✅ | `domain/normalization.py` is pure data + policy functions |
| All DuckDB/Parquet via the data-engine layer | ✅ | detection SQL + view DDL live in `engine/`; repository calls store methods only |
| Agentic layer prompt-driven, prompts versioned | ✅ n/a | no model calls anywhere in this feature (AC-12 mandates it) |
| Normalization rules never silently applied | ✅ | approval endpoints are the only apply path; AC-5 pins it; mutation gate planned |
| Ingestion idempotent, profiling reproducible | ✅ | detection is read-only; apply/revoke re-profile the same view deterministically |
| API thin, no business logic | ✅ | routes delegate to repository; schemas map domain objects |
| uv-only backend, typed, ruff | ✅ | standard stack, no new deps |
| Autonomy stance | high (in-session delegation), matched by non-default validation_method (messy-fixture board + mutation gates + browser e2e) |
| Verification independence | boards generated from spec.md; unit tests separate; mutation pass at CP8 |
| Mutation policy | explicit gates: (1) remove approval gate → AC-5 red; (2) drop dismissed-persistence → AC-8 red; (3) break canonical tie-break → AC-4/6 red |
| Performance budgets | see section below |

**Amendments:** none required. One clarification recorded: the charter lists
normalization detection under the *agentic layer's* ownership; v1 implements
it as deterministic engine-layer detection because the approved AC-12
requires identical offline behavior (no model calls). The agentic layer
remains the owner of future judgment-based extensions (fuzzy merges,
abbreviation folding — out of scope per acs.md). No charter rule is
violated; the capability moved down a layer, the invariants hold.

## Phasing

1. **Domain + detection** — pure policy + engine `detect`; unit-first; bind
   the 6 detection scenarios (AC-1..4, AC-12×2).
2. **Lifecycle** — store view overlay, repository approve/dismiss/revoke,
   sidecar persistence, boot/refresh re-assert, re-profile; bind the 7
   lifecycle scenarios (AC-5..10 + not-found).
3. **API + fixtures parity** — routes, schemas, 404 mapping, seeded fixture
   proposal + mutable fixture state; route-level unit tests.
4. **Workbench UI** — indicator, drilldown card, actions; bind the 2
   browser scenarios; board 15/15.
5. **Harden** — mutation gates above, lint/mypy, full boards, docs touch
   (user manual "Normalization" section if time allows).

## Performance budgets

- Detection: ≤1 GROUP BY per candidate column, candidates bounded
  (text-typed, distinct ≤ 200, ratio ≤ 0.5); on a 1M-row × 30-column file
  that is a handful of indexed-scan aggregations — target < 2s cold, and it
  runs only on explicit request.
- Apply/revoke: one `CREATE OR REPLACE VIEW` + one re-profile — target < 1s
  on the same scale.
- Zero impact on ingest latency and on datasets nobody inspects.

## Collaboration schedule

Autonomous session (owner AFK): no mid-checkpoint pauses; handoffs per
checkpoint; owner reviews post-hoc via PR. Stop-conditions: a charter
deviation needing an amendment, or a spec contradiction — neither expected.

## Execution modes

Planner and implementer both run locally in-session (implementer proceeds
immediately under the standing delegation); refine/verify as usual; PR
squash-merge at the end.

## Test strategy

Per `feature.md.validation_method`: the generated acceptance board over
messy fixture CSVs is the WHAT-gate (15 scenarios, currently red); unit
tests cover the detector's edges (nulls, unicode casefold, ties, empty
columns, near-unique exemption), the view overlay SQL, sidecar round-trip,
and route status codes; the three named mutation gates prove the tests bite
(run at CP8 with the standard boards + lint + mypy). Browser e2e covers the
workbench flow against seeded fixtures. No live-model or network dependence
anywhere in the board.
