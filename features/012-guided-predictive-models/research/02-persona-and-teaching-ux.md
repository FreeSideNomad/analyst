# 02 — Persona and the teaching UX

## The audience (the user's own definition, verbatim in substance)

People like the product owner: **can learn terminology and concepts, but
will not do the messy work** — no Python, no SQL, no hand-built feature
tables, no invoking training functions. The LLM does the mechanics, or a
simple UI exposes algorithm parameters. Assume the user knows roughly
**basic linear regression and nothing more**; the product must explain
everything else *as it goes*.

This is the same bet the rest of analyst makes: feature 003 exists because
people who can't write SQL still deserve trustworthy queries; this feature
says people who can't write scikit-learn pipelines still deserve trustworthy
models.

## Design consequences

1. **The agent does all the mechanics.** Label SQL, feature tables, splits,
   training runs. Code is never shown unless the trust trail is expanded —
   the same layering as the SQL tab today: hidden, always inspectable.
2. **Concepts are taught at the moment they matter, in decision form.** No
   lectures. An out-of-time split is taught as an AskQuestion: *"To test the
   model honestly, I'll hide everything after March 2026 and predict it as
   if I were living in the past. Sound right, or pick a different cutoff?"*
   The user learns the concept by deciding it.
3. **Numbers arrive with meaning attached.** Not "AUROC 0.76" but "given one
   account that churned and one that didn't, the model picks the right one
   76% of the time — a coin flip is 50%". Not "RMSE 19,400" but "off by
   about $19k on a typical house".
4. **Parameters get a simple UI with agent-chosen defaults.** Nudging them
   is optional curiosity, never required work. The UI edits the same bounded
   parameter schema the agent fills (research/05) — one mechanism, two hands
   on it.
5. **Everything is explainable as "linear regression, plus upgrades."**
   Nonlinear splits, many weak learners combined, honest testing — three
   steps from the one concept the persona already holds.
6. **The trust trail leads with business-phrased measures** (top-100
   capture, plain-English ranking quality) and keeps the full statistical
   table one expand away — same layering as answer → SQL.

## Metric explainers (developed in discussion; reuse in the product)

**AUROC** — Area Under the Receiver Operating Characteristic curve. Measures
*ranking* quality: grab one true positive and one true negative; how often
does the model score the positive higher? 1.0 perfect, 0.5 coin flip.
Threshold-free, which is why research defaults to it.

**Threshold measures** (after choosing a cutoff; from the confusion matrix):
- **Precision** — of everyone flagged, how many were right? (Cost of crying
  wolf.)
- **Recall** — of everyone who was truly positive, how many did we catch?
  (Cost of missing.)
- **F1** — one number balancing precision and recall.
- **Accuracy** — fraction correct overall. *Mostly a trap*: with 5% churn,
  "nobody ever churns" is 95% accurate and useless.

**Average Precision / PR-AUC** — the honest measure on rare events; focuses
on how clean the top of the ranked list is. relgraph's churn model: AUROC
0.90 but AP 0.35 — a great ranker whose flagged list still holds plenty of
false alarms. Report both.

**Calibration** (Brier score, calibration curves) — does a score of 0.8 mean
80% actually happen? A model can rank perfectly yet be systematically
overconfident; matters whenever scores feed thresholds ("exposure to
customers above 0.8").

**Lift / precision@k** — "if the retention team can call only 100 customers,
how many real churners are in the model's top 100 versus picking at random?"
Often the most honest measure for this persona: phrased in actions.

**Regression:** **MAE** (average miss in real units), **RMSE** (like MAE but
punishes big misses harder), **R²** (fraction of variation explained — the
one the persona knows from linear regression).
