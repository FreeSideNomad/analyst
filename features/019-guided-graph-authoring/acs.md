---
ac_count: 12
high_priority_count: 9
discovered: 2026-07-19
---

# Acceptance criteria — 019 guided-graph-authoring

> Greenfield discovery, autonomous session (owner decisions locked at
> promotion; owner engaged interactively on scope — the connected-DB use
> case is theirs). Grounded in the shipped 018 engine and the owner's
> paper. Four passes covered: happy path AC-1–7, edge AC-8, errors AC-9,
> cross-cutting AC-10–12. Deploy-model checklist: container gate carries
> it (AC-12).

## AC-1: Berka arrives as a connected relational database
Priority: high · Type: happy-path

A user whose linked data lives in a relational database — the likeliest
home for it — connects that database (the curated Berka data seeded into
the demo Postgres stands in for it). The tables are profiled and
catalogued in place and the links between them are validated against the
data, exactly as with uploads. Nothing is copied at connect time.

## AC-2: The graph structure is derived from what the workspace knows
Priority: high · Type: happy-path

Asking for a relational model on suitable linked data — uploaded or
connected — needs no schema work from the user: the structure the graph
will learn from (which tables, which validated links, which time column)
is derived mechanically from the existing catalog and shown in plain
language before anything trains. Every link used is one the workspace has
already validated; none are invented.

## AC-3: Task decisions are authored with guidance and confirmed
Priority: high · Type: happy-path

The user states what they want to predict in their own words; the agent
turns it into concrete decisions — the entity being predicted, the exact
outcome definition, the prediction moment and horizon, the honest time
cutoffs, and the columns that must be hidden because they record the
outcome. Each decision is presented in plain language and the user
confirms or adjusts before training; nothing runs unconfirmed.

## AC-4: The connected-database path reproduces the curated reference
Priority: high · Type: happy-path

Driving the guided flow on Berka-in-Postgres reproduces the curated 018
bundle's results on the same tasks within the established tolerances
(baseline ±0.03, graph ±0.07, deterministic seeds). Same data, different
arrival path, same models.

## AC-5: The uploaded-files path reproduces the curated reference
Priority: high · Type: happy-path

The same equivalence holds when the Berka tables arrive as ordinary file
uploads: the generated flow must match what the hand-curated bundle
produces. The curated artifacts are the ground truth for the generator.

## AC-6: Outcome columns cannot reach the model
Priority: high · Type: happy-path

Every column the outcome definition reads is excluded automatically and
shown to the user as hidden; asking to include one back is refused with
the reason. If a single remaining column alone can nearly perfectly
predict the outcome, the user is warned it likely records the outcome.

## AC-7: The wiring is provably honest on any dataset
Priority: high · Type: happy-path

Where no reference numbers exist, honesty is structural: training on
deliberately shuffled outcomes scores as a coin flip (no leak in the
plumbing), and the same seed always reproduces the same result.

## AC-8: Unsuitable data is refused with reasons
Priority: medium · Type: edge-case

A workspace without validated links, without a usable time column, or
running without the ML runtime is refused before anything trains, with
the missing prerequisites named plainly. (Extends 018's guard to
generated flows.)

## AC-9: A failed authoring or training run leaves nothing behind
Priority: medium · Type: error

If guidance fails, a decision is rejected, or training errors, the
failure is reported plainly and the registry and workspace are exactly as
before.

## AC-10: The agent sees decisions, never data
Priority: high · Type: cross-cutting

The authoring exchange carries schema, catalog descriptions and profile
facts only — never rows from the user's tables. The outcome definition
executes locally under the same read-only SQL guard as every query.

## AC-11: The registry discloses the source and the local build
Priority: medium · Type: cross-cutting

A trained model's story names where the data came from (which connection
or files) and states plainly that training materialized a temporary local
copy of the connected tables — local, never leaving the machine.

## AC-12: The full journey passes against the deployed ML container
Priority: high · Type: cross-cutting

The complete journey — connect the seeded database, author the task with
guidance, train, see predictions and the registry story — passes in a
browser against the deployed analyst:ml container with the demo database
running alongside. The owner takes over exploratory testing at this gate.
