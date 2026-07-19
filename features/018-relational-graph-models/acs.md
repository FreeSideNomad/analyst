---
ac_count: 14
high_priority_count: 10
discovered: 2026-07-19
---

# Acceptance criteria — 018 relational-graph-models

> Greenfield discovery, autonomous session (owner decisions locked at
> promotion). Grounded in the owner's paper (`~/code/relational-graph`):
> reference numbers from RESULTS.md, task design from
> `datasets/berka/tasks/*.yaml`, temporal honesty from the task specs
> (outcomes recorded after the prediction date are hidden from models).
> Four interview passes covered: happy path (AC-1–9), edge cases
> (AC-10–11), errors (AC-12), cross-cutting (AC-13–14). Deploy-model
> checklist consulted — image-variant expectations folded into AC-10/14.

## AC-1: The Berka reference bundle arrives through the normal pipeline
Priority: high · Type: happy-path

From the sample gallery, one click brings in the Berka banking dataset
(PKDD'99): all its tables land through the ordinary ingestion pipeline —
profiled, catalogued, and queryable — with the relationships between them
(accounts, loans, transactions, clients, districts, cards, orders) present
in the workspace as validated links. The data is downloaded on demand from
public sources, cached locally, and never stored in the repository; adding
it again is instant and works offline from the cache.

## AC-2: A relational prediction task is defined as decisions, not code
Priority: high · Type: happy-path

The user picks a relational prediction task (e.g. "will this loan end in
default?") and the app frames it in plain language: what is being
predicted, for which entities, as of which moment. Temporal honesty is
presented as part of the framing: the prediction is made from information
available at that moment, and columns that record the outcome afterwards
are named and excluded. No code, SQL, or graph terminology is required
from the user.

## AC-3: Graph training is local and deterministic
Priority: high · Type: happy-path

Training the graph model runs entirely on the user's machine. Training the
same task twice with the same seed reports identical evaluation scores.

## AC-4: The graph model reproduces the paper's reference results
Priority: high · Type: happy-path

On the Berka tasks, the graph model's held-out AUROC lands within a small
stated tolerance of the paper's published numbers (loan_default 0.7182,
account_churn 0.7592, card_adoption 0.6787). This is the code-validity
gate: single flat tables cannot exercise a graph, so correctness is
demonstrated by reproducing known results on real relational data.

## AC-5: The relational-feature baseline reproduces its reference results
Priority: high · Type: happy-path

The simple tier — relational features aggregated into a flat table and
trained with the same gradient-boosting approach as feature 012 — lands
within tolerance of the paper's baseline numbers (loan_default 0.7647,
account_churn 0.9018, card_adoption 0.7999) on the same honest split. The
comparison between tiers is reported truthfully, including when the simple
approach wins (the paper's own finding on public data).

## AC-6: The hybrid tier is trained and honestly compared
Priority: high · Type: happy-path

A hybrid model (the graph model's learned representations fed into the
gradient-boosting model) trains deterministically on the same split and is
evaluated alongside the other two tiers. Its held-out score is reported in
the same registry card, and it is no worse than a small stated margin
below the stronger of its two parents — the guard that the combination is
wired correctly rather than degrading both.

## AC-7: Predictions become an ordinary dataset
Priority: high · Type: happy-path

A trained relational model writes its predictions back as a normal
dataset — one row per entity with the actual outcome, the predicted
likelihood, and whether that row was held out — queryable, chartable, and
exportable like anything else.

## AC-8: The registry tells the relational story
Priority: high · Type: happy-path

The registry card for a relational model names, in plain language: the
task, the tables and links the graph learned from, how the honest split
was made (by time), the seed, the sizes of the training and held-out sets,
and each tier's scores. A reader who knows no ML vocabulary can tell what
the model saw and how good it is.

## AC-9: Relational models survive a restart
Priority: medium · Type: happy-path

After the app restarts, the registry still lists the relational model with
its metrics and story, and its predictions dataset is still queryable.

## AC-10: Without the ML runtime, the tier degrades honestly
Priority: high · Type: edge-case

The default (lean) distribution does not carry the heavy ML runtime. In
it, the relational tier says plainly that graph training needs the ML
variant of the app and how to get it — while everything else, including
feature 012's single-table models, keeps working. In the ML variant,
the relational tier is fully available. The lean image does not grow by
the ML runtime's size.

## AC-11: An unsuitable workspace is refused with a reason
Priority: medium · Type: edge-case

Asking for a relational model on data that cannot support one — no
validated links between tables, or no time column to split honestly by —
is refused before any training starts, with a plain-language explanation
of what is missing.

## AC-12: A failed training run leaves nothing behind
Priority: medium · Type: error

If training fails or is interrupted, the failure is reported plainly and
the registry contains no partial model; the workspace is exactly as it
was before the attempt.

## AC-13: Bulk data never leaves the machine
Priority: high · Type: cross-cutting

All training and evaluation runs locally. Any agent exchange involved in
guiding the task carries only schema, catalog descriptions, and profile
facts — never account, transaction, or client records.

## AC-14: The full journey passes against the deployed ML container
Priority: high · Type: cross-cutting

The complete journey — add Berka, define the loan-default task, train,
see the registry card and predictions dataset — passes in a browser
against the deployed ML-variant container image, built and run exactly as
a user would run it. This is the autonomy gate: the owner takes over
exploratory testing once it is green.
