# 05 — Architecture direction: declarative artifacts, not generated scripts

> Answers the product owner's direct question: *"How do you envisage doing
> B? LLM creates scripts we store and execute locally?"* — **No.** The LLM
> never produces code we execute. It fills declarative, validated artifacts;
> committed engine code executes them. Feature 003 already set this
> precedent, and the charter mandates most of it.

## The pattern (extending feature 003)

Feature 003's planner: the LLM emits a **structured plan** (SQL +
assumptions + confidence), our code validates it against the catalog, and
only then executes it in DuckDB. AC-5 pins the guarantee: *a plan
referencing unknown columns is never executed*. The Models area is the same
pattern with three artifact kinds:

### 1. Task definition — a structured spec, not a script

```yaml
entity: house
target: SalePrice
task_type: regression            # regression | binary (binary post-MVP)
split:
  method: random                 # random | out_of_time (post-MVP)
  holdout: 0.2
  seed: 42
# out_of_time variant: {method: out_of_time, cutoff: 2026-01-01, horizon: 90d}
```

Stored as a versioned artifact in the workspace, like a saved query.
**relgraph already proved this format** — its `tasks/*.yaml` (entity + label
SQL + horizon) is precisely this; analyst generates it conversationally
instead of by hand.

### 2. Anything data-shaped is SQL — generated, then validated, then run

Label queries, feature expressions, split materialization. LLM-generated,
but gated before execution:

- schema-checked against the catalog (unknown column → rejected),
- dry-run in DuckDB,
- leakage-guarded (post-MVP temporal tasks: SQL touching data after the
  as-of date is rejected),
- rejection → AskQuestion, never silent guessing.

Then executed **locally by the data-engine layer** (the charter forbids raw
DuckDB outside it). This SQL is what the trust trail's SQL tab shows.

### 3. Training is OUR code, never generated code

A fixed, committed, unit-tested engine function —
`train(task_spec, feature_table, params)` around scikit-learn/LightGBM. The
LLM's only influence is choosing `params` **within a bounded schema**; the
simple parameter UI edits the same schema. One mechanism, whether the agent
or the user turns the knobs.

## What gets stored: a reproducible bundle

`task spec + validated SQL + params + training-data fingerprint` — 
deterministically rerunnable, rendered as the model's trust trail, and
testable with the existing cassette record/replay (structured outputs
replay cleanly; generated Python would not).

## The hard line, and its honest cost

**No arbitrary code execution, ever.** relgraph needed an escape hatch
(`hooks.py`) for parsing that couldn't be declarative; analyst v1 refuses
the hatch — if the agent cannot express a feature in validated SQL, it says
so and moves on. DuckDB SQL is expressive enough that this bites rarely, and
the line buys: auditability, determinism, cassette-replayable tests, and no
new attack surface.

## Charter hooks (why this design is forced, not chosen)

- "Prompts and their expected structured outputs are **versioned
  artifacts**."
- "All Parquet/DuckDB access goes through the **data-engine layer**."
- "Discovered relationships … are test-validated candidates, **never
  silently applied**" — extended here to generated SQL and to feature joins.
- **Governance invariant untouched:** training/scoring run locally; only
  schema, profiles, capped samples, and small results cross to the LLM. A
  model trained on 30M rows never sends those rows anywhere.

## Scope/dependency notes

- **Charter/PRD amendment required:** current scope reads ingest → profile →
  catalog → *answer questions*; predictive modeling extends it. Charter
  changes are PR'd and human-approved — fold the amendment into this
  feature's plan checkpoint (flagged in feature.md).
- **Deps:** MVP adds scikit-learn + LightGBM (small, CPU-only, fine for the
  single image). torch/torch-frame/GNN stack belongs to the graph-backend
  feature, likely as an optional image variant — keeping the default image
  slim is a distribution constraint (multi-arch ghcr publishing exists
  today).
- **Vault reuse:** Kaggle API token (gallery, post-MVP) is a credential →
  feature-011 encrypted vault, not a new mechanism.
