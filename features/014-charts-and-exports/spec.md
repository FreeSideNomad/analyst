# Spec — Feature 014: Charts & data exports

> Checkpoint 3. Standard Gherkin over the 11 approved ACs in `acs.md`.
> Chart-lifecycle and export scenarios bind over the in-process seam (real
> store + service in the scenario tmp_path; "the app restarts" rebuilds the
> stack); the save/open/override flows also bind to a real browser against
> the fixtures app. Deterministic — reopening a chart executes its stored
> query, no planning, no model calls. Each scenario is tagged with its AC.

Feature: Charts & data exports
  An answer can be kept as a named chart that re-runs its query against
  current data whenever it is opened — never a stale snapshot — with its
  trust trail intact and its presentation overridable. Result sets and
  datasets export locally to CSV, Parquet, or Excel at full fidelity.

## Chart type inference (in-process)

  # AC-1
  Scenario: A time-series aggregate presents as a line chart
    Given an ingested file of monthly totals across six months
    When the user's question computes the total by month
    Then the answer presents as a line chart

  # AC-1
  Scenario: A categorical aggregate still presents as a bar chart
    Given an ingested sales file where case variants of "East" carry amounts 10, 20 and 30 and "West" carries 40 and 50
    When the user's question computes the total amount by region
    Then the answer presents as a bar chart

## Saved charts (in-process)

  # AC-3
  Scenario: An answer is saved as a named chart
    Given an ingested sales file where case variants of "East" carry amounts 10, 20 and 30 and "West" carries 40 and 50
    And an answered question computing the total amount by region
    When the user saves the answer as a chart named "Revenue by region"
    Then the workspace lists a saved chart named "Revenue by region"

  # AC-4
  Scenario: Opening a saved chart shows the chart and its trust trail
    Given an ingested sales file where case variants of "East" carry amounts 10, 20 and 30 and "West" carries 40 and 50
    And a saved chart named "Revenue by region" computing the total amount by region
    When the user opens the saved chart
    Then the chart shows "West" totalling 90
    And the chart carries a trust trail disclosing its query

  # AC-5
  Scenario: A saved chart re-runs against current data when opened
    Given an ingested sales file where case variants of "East" carry amounts 10, 20 and 30 and "West" carries 40 and 50
    And a saved chart named "Revenue by region" computing the total amount by region
    When the dataset is refreshed so "West" carries 400 instead
    And the user opens the saved chart
    Then the chart shows "West" totalling 400

  # AC-6
  Scenario: A saved chart can be renamed and deleted
    Given an ingested sales file where case variants of "East" carry amounts 10, 20 and 30 and "West" carries 40 and 50
    And a saved chart named "Revenue by region" computing the total amount by region
    When the user renames the saved chart to "Regional revenue"
    Then the workspace lists a saved chart named "Regional revenue"
    When the user deletes the saved chart
    Then the workspace lists no saved charts

  # AC-10
  Scenario: Saved charts survive a restart
    Given an ingested sales file where case variants of "East" carry amounts 10, 20 and 30 and "West" carries 40 and 50
    And a saved chart named "Revenue by region" computing the total amount by region
    When the app restarts
    Then the workspace lists a saved chart named "Revenue by region"
    And opening it shows "West" totalling 90

  # AC-10
  Scenario: A chart whose dataset is gone fails clearly and stays deletable
    Given an ingested sales file where case variants of "East" carry amounts 10, 20 and 30 and "West" carries 40 and 50
    And a saved chart named "Revenue by region" computing the total amount by region
    When the dataset is deleted
    And the user opens the saved chart
    Then the chart reports that its data is gone
    And the user can still delete the saved chart

  # AC-11
  Scenario: Reopening a chart is local and does not re-plan
    Given the app runs offline with no AI features available
    And an ingested sales file where case variants of "East" carry amounts 10, 20 and 30 and "West" carries 40 and 50
    And a saved chart named "Revenue by region" computing the total amount by region
    When the user opens the saved chart
    Then the chart shows "West" totalling 90

## Exports (in-process)

  # AC-7
  Scenario: An answer's result exports to CSV and Excel
    Given an ingested sales file where case variants of "East" carry amounts 10, 20 and 30 and "West" carries 40 and 50
    And a saved chart named "Revenue by region" computing the total amount by region
    When the user exports the chart's result as CSV and as Excel
    Then each export's header names the result's columns
    And each export's rows carry "West" with 90

  # AC-8
  Scenario: A dataset exports to CSV, Parquet, and Excel
    Given an ingested sales file where case variants of "East" carry amounts 10, 20 and 30 and "West" carries 40 and 50
    When the user exports the dataset in each of the three formats
    Then every export carries all 5 rows of the dataset

  # AC-8 (ties to 013)
  Scenario: A dataset export reflects an approved normalization
    Given an ingested sales file where case variants of "East" carry amounts 10, 20 and 30 and "West" carries 40 and 50
    And the proposed rule for column "region" is approved
    When the user exports the dataset as CSV
    Then the export's "region" values are only "East" and "West"

  # AC-9
  Scenario: Exports are never truncated by the display cap
    Given an ingested file with more rows than the display cap
    When the user exports the dataset as CSV
    Then the export carries every row while the on-screen table is capped

  # AC-11 (folded errors)
  Scenario: Acting on a chart or dataset that does not exist fails cleanly
    Given an ingested sales file where case variants of "East" carry amounts 10, 20 and 30 and "West" carries 40 and 50
    When the user opens a saved chart that does not exist
    Then the action is rejected as not found
    When the user exports a dataset that does not exist
    Then the action is rejected as not found

## Workbench flows (browser)

  # AC-2 + AC-3
  Scenario: Saving an answer as a chart from the thread
    Given the analyst app is open in a browser
    And the user has an answered revenue question in the thread
    When the user switches the answer's presentation to a line chart
    And the user saves the answer as a chart named "Regional revenue"
    Then the Charts area lists "Regional revenue"

  # AC-4 + AC-2
  Scenario: Opening a saved chart from the Charts area
    Given the analyst app is open in a browser
    And a saved chart named "Regional revenue" exists in the workspace
    When the user opens "Regional revenue" from the Charts area
    Then the chart renders with its trust trail available
    And the user can switch its presentation to a table
