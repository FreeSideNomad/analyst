---
ac_count: 11
high_priority_count: 7
discovered: 2026-07-15
mode: greenfield
note: >
  Autonomous session (owner AFK, full autonomy delegated in-session). Four
  interview passes self-answered from feature.md, the charter, the roadmap
  note, and the existing Q&A answer machinery; decisions recorded here.
---

# Acceptance criteria — 014 charts & data exports

Scope decisions (recorded in lieu of the interview):

- **A saved chart is a saved question, not a picture.** It stores the
  question, the validated query, and the chart configuration; opening it
  re-runs the query against current data. No snapshots.
- **Chart types v1:** stat, bar, line, table. Line is inferred when the
  x-axis is temporal; the user can override the presentation at any time.
- **Exports are full-fidelity and local.** The on-screen table may be
  truncated; the exported file never is. Formats: CSV + Excel for answer
  results; CSV + Parquet + Excel for datasets. Nothing about an export
  crosses to the model.
- Saved charts live per workspace and survive restarts, like every other
  workspace artifact.

## AC-1: Chart type is inferred, including line for time series

Priority: Medium · Type: happy-path

An aggregate answer whose category axis is temporal (e.g. monthly totals)
arrives as a line chart; non-temporal aggregates arrive as bar; single
values as a stat — the inference is visible in how the answer renders.

## AC-2: The user can override how an answer is presented

Priority: High · Type: happy-path

On any charted answer the user can switch the presentation between the
inferred chart, the other chart type, and the table — without re-asking the
question, and the trust trail stays attached throughout.

## AC-3: An answer can be saved as a named chart

Priority: High · Type: happy-path

From an answered question the user saves the result as a chart with a name;
the save confirms without leaving the thread.

## AC-4: Saved charts are listed and reopenable

Priority: High · Type: happy-path

A Charts area lists the workspace's saved charts by name; opening one shows
the chart in its saved presentation together with its trust trail
(assumptions, lineage, the query).

## AC-5: Opening a saved chart re-runs its query against current data

Priority: High · Type: happy-path (the anti-snapshot pin)

After the underlying dataset is refreshed with different data, opening the
saved chart shows the NEW numbers — a saved chart is never a stale
snapshot.

## AC-6: Saved charts can be renamed and deleted

Priority: Medium · Type: happy-path

Renaming changes the listed name; deleting removes the chart from the list
— neither touches the underlying data.

## AC-7: An answer's result exports to CSV and Excel

Priority: High · Type: happy-path

From an answer's result the user downloads a CSV or Excel file whose header
matches the result's columns and whose rows match the result's values.

## AC-8: A dataset exports to CSV, Parquet, and Excel

Priority: High · Type: happy-path

From a dataset in the workbench the user downloads the full dataset in any
of the three formats; the file's contents match what queries see (an
approved normalization, for instance, is reflected).

## AC-9: Exports are never truncated

Priority: High · Type: edge-case

When the on-screen result table is capped for display, the exported file
still contains every row of the result.

## AC-10: Saved charts survive a restart; a broken chart fails clearly

Priority: High · Type: cross-cutting

Saved charts are still listed and openable after the app restarts. A saved
chart whose dataset no longer exists opens to a clear "its data is gone"
message — never a crash — and can still be deleted.

## AC-11: Everything here is local

Priority: Medium · Type: cross-cutting/governance

Saving, reopening, and exporting run entirely locally with no model calls —
identical behavior in an offline deployment. (Re-running a saved chart
executes its stored, validated query; it does not re-plan.)

## Errors (folded)

Opening, renaming, or deleting a chart that does not exist — and exporting
a dataset that does not exist — fail with a clear not-found message and
change nothing. Pinned at the API level during implementation.
