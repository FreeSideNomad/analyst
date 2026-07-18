# Spec — Feature 015: Interactive dashboards

> Checkpoint 3. Standard Gherkin over the 13 approved ACs in `acs.md`.
> Assembly/editing replay a recorded cassette (deterministic, no live model
> in the board); viewing/filtering scenarios run fully offline; the
> workbench flows bind to a real browser against the fixtures app. Each
> scenario is tagged with its AC.

Feature: Interactive dashboards
  A user describes the dashboard they want in plain English; the agent
  assembles it as a grid of widgets — each a saved-chart-shaped question
  with its trust trail. The dashboard is interactive: a shared filter
  re-scopes every widget, clicking a chart cross-filters the others,
  presentations switch per widget, and drill-down opens the underlying
  rows. Dashboards persist, re-run live, and stay entirely local to view.

## Assembling (in-process, recorded agent turns)

  # AC-1
  Scenario: A plain-English request assembles a dashboard
    Given an ingested regional sales file
    When the user asks for "a sales overview dashboard"
    Then a named dashboard is assembled with at least two widgets
    And every widget renders from locally computed numbers

  # AC-2
  Scenario: An under-specified request asks before assembling
    Given an ingested regional sales file
    When the user asks for "a dashboard about performance"
    Then the agent asks a structured clarification instead of assembling

  # AC-3
  Scenario: Every widget carries its trust trail
    Given an ingested regional sales file
    And an assembled sales overview dashboard
    Then each widget disclosed its assumptions, lineage and query

  # AC-12
  Scenario: Assembly keeps bulk data local
    Given an ingested regional sales file
    When the user asks for "a sales overview dashboard"
    Then the exchange sent for assembly carries schema and catalog metadata
    And the exchange carries no data rows

  # AC-13
  Scenario: A malformed assembly is rejected whole
    Given an ingested regional sales file
    And the next assembly will produce an invalid widget query
    When the user asks for "a sales overview dashboard"
    Then the assembly is rejected with the reason
    And no dashboard is created

## Viewing, filtering, drilling (in-process, fully offline)

  # AC-4
  Scenario: A shared filter re-scopes every widget
    Given an ingested regional sales file
    And an assembled sales overview dashboard
    When the user filters the dashboard to region "East"
    Then the revenue widget totals only the East rows
    And clearing the filter restores the original totals

  # AC-4
  Scenario: A widget without the filtered dimension says so
    Given an ingested regional sales file
    And an assembled sales overview dashboard
    When the user filters the dashboard to region "East"
    Then the widget lacking a region indicates it is unaffected

  # AC-5
  Scenario: Clicking a chart cross-filters the others
    Given an ingested regional sales file
    And an assembled sales overview dashboard
    When the user clicks the "East" bar of the revenue widget
    Then the other widgets re-scope to the East rows
    And the active filter is visible and clearable in one action

  # AC-7
  Scenario: Drill-down opens the rows behind a widget
    Given an ingested regional sales file
    And an assembled sales overview dashboard
    When the user drills into the revenue widget under the "East" filter
    Then the drill shows only East source rows

  # AC-9
  Scenario: Dashboards persist and re-run live
    Given an ingested regional sales file
    And an assembled sales overview dashboard
    When the dataset is refreshed with doubled amounts
    And the app restarts
    Then the dashboard is still listed
    And opening it shows the doubled totals

  # AC-10
  Scenario: A broken widget fails alone
    Given an ingested regional sales file
    And an assembled sales overview dashboard
    When the sales dataset is deleted
    Then opening the dashboard reports each widget's data as gone
    And the dashboard itself still opens and can be deleted

  # AC-11
  Scenario: Viewing is local; authoring degrades honestly
    Given the app runs offline with no AI features available
    And a previously assembled sales overview dashboard
    Then opening and filtering the dashboard still works
    And asking for a new dashboard fails with a plain message

  # AC-8 + AC-6
  Scenario: A dashboard is edited conversationally
    Given an ingested regional sales file
    And an assembled sales overview dashboard
    When the user asks to "add a widget showing the row count by region"
    Then the dashboard gains the requested widget
    And removing a widget shrinks the dashboard
    And a widget's presentation can be switched without affecting the others

## Workbench flows (browser)

  # AC-1 + AC-4
  Scenario: Assembling and filtering a dashboard in the workbench
    Given the analyst app is open in a browser
    When the user opens the Dashboards area
    And the user requests "a sales overview dashboard"
    Then a dashboard renders with its widgets
    When the user filters to region "East"
    Then the widgets update without a page reload

  # AC-5 + AC-7
  Scenario: Cross-filter and drill in the workbench
    Given the analyst app is open in a browser
    And a sample dashboard is open in the Dashboards area
    When the user clicks a bar of the first widget
    Then the active filter chip appears
    When the user drills into the first widget
    Then the underlying rows are shown
