# Spec — Feature 016: Catalog curation

> Checkpoint 3. Standard Gherkin over the 12 approved ACs in `acs.md`.
> Curation scenarios bind over the in-process seam; agent-completed
> synthesis replays a recorded cassette (deterministic, no live model in
> the board); the workbench flows bind to a real browser against the
> fixtures app. Each scenario is tagged with its AC.

Feature: Catalog curation
  A clarification in the catalog is a real question the user can answer —
  with an offered option or their own words — and the answer completes the
  semantic analysis. Any description accepts a suggested correction. Human-
  settled meanings are recorded, bounded in their effect, and never
  silently overwritten.

## Answering clarifications (in-process)

  # AC-1
  Scenario: A clarification offers its options and accepts a free-form answer
    Given an ingested orders file whose catalog asks what the "status" column describes
    When the user reviews the open clarifications
    Then the clarification offers its options and accepts a custom answer

  # AC-2
  Scenario: Answering with an option settles the column's meaning
    Given an ingested orders file whose catalog asks what the "status" column describes
    When the user answers the clarification with "Fulfillment state of a sale or order"
    Then the "status" column's description states the fulfillment meaning
    And no clarification remains open for the dataset

  # AC-3
  Scenario: A free-form answer is equally authoritative
    Given an ingested orders file whose catalog asks what the "status" column describes
    When the user answers the clarification in their own words: "Stage of the returns process"
    Then the "status" column's description reflects the returns-process meaning

  # AC-4
  Scenario: Curation touches at most the column and its own table
    Given an ingested orders file whose catalog asks what the "status" column describes
    And a second ingested customers file with its own catalog
    When the user answers the clarification with "Fulfillment state of a sale or order"
    Then the customers catalog is entirely unchanged
    And only the "status" column and the orders table description may differ

  # AC-5
  Scenario: A settled meaning carries its provenance
    Given an ingested orders file whose catalog asks what the "status" column describes
    When the user answers the clarification with "Fulfillment state of a sale or order"
    Then the "status" column is marked human-confirmed
    And the recorded provenance carries the given answer

  # AC-6
  Scenario: A settled meaning survives re-cataloguing and a restart
    Given an ingested orders file whose catalog asks what the "status" column describes
    And the clarification is answered with "Fulfillment state of a sale or order"
    When the dataset is re-catalogued automatically
    And the app restarts
    Then the "status" column's description still states the fulfillment meaning
    And the column is still marked human-confirmed

## Suggesting corrections (in-process)

  # AC-7
  Scenario: A column description accepts a suggested correction
    Given an ingested orders file with a catalogued "order_date" column
    When the user suggests the correction "This is the settlement date, not the order date"
    Then the "order_date" column's description reflects the settlement meaning
    And the column is marked human-confirmed

  # AC-7
  Scenario: A table description accepts a suggested correction
    Given an ingested orders file with a catalogued "order_date" column
    When the user suggests the table correction "These are wholesale transactions only"
    Then the orders table description reflects the wholesale meaning
    And the table is marked human-confirmed

  # AC-8
  Scenario: Offline, a clarification answer still settles the meaning
    Given the app runs offline with no AI features available
    And an ingested orders file whose catalog asks what the "status" column describes
    When the user answers the clarification with "Fulfillment state of a sale or order"
    Then the "status" column's description plainly records the chosen meaning
    And the column is marked human-confirmed and awaiting reconciliation
    And no clarification remains open for the dataset

  # AC-8
  Scenario: Offline, a correction applies the user's words verbatim
    Given the app runs offline with no AI features available
    And an ingested orders file with a catalogued "order_date" column
    When the user suggests the correction "This is the settlement date, not the order date"
    Then the "order_date" column's description is exactly the suggested words
    And the column is marked human-confirmed and awaiting reconciliation

  # AC-9
  Scenario: A settled meaning sharpens the next answer
    Given an ingested orders file whose catalog asks what the "status" column describes
    And the clarification is answered with "Fulfillment state of a sale or order"
    When the user asks which orders are not yet fulfilled
    Then the answer counts only the orders whose status is unfulfilled

  # AC-11
  Scenario: Curation keeps bulk data local
    Given an ingested orders file whose catalog asks what the "status" column describes
    When the user answers the clarification with "Fulfillment state of a sale or order"
    Then the exchange sent for completion carries profile facts, catalog text and the answer
    And the exchange carries no data rows

  # AC-12
  Scenario: Curation errors are clean
    Given an ingested orders file whose catalog asks what the "status" column describes
    When the user submits an empty answer
    Then the submission is rejected with a message
    When the user answers a clarification that does not exist
    Then the action is rejected as not found
    And the catalog is unchanged

  # AC-12
  Scenario: A failed completion leaves the catalog untouched
    Given an ingested orders file whose catalog asks what the "status" column describes
    And the semantic analysis will fail on the next attempt
    When the user answers the clarification with "Fulfillment state of a sale or order"
    Then the failure is reported plainly
    And the catalog is unchanged and the clarification remains open

## Workbench flows (browser)

  # AC-10 + AC-1
  Scenario: Answering a clarification in the workbench
    Given the analyst app is open in a browser
    When the user opens the sample transactions table in the workbench
    And the user answers its open clarification with the canonical-name option
    Then the clarification disappears without a page reload
    And the settled column shows a human-confirmed badge

  # AC-10 + AC-7
  Scenario: Correcting a column meaning in the workbench
    Given the analyst app is open in a browser
    When the user opens the column "billing_region" of the sample sales table
    And the user suggests the correction "Region of the customer's billing address"
    Then the column shows a human-confirmed badge without a page reload
