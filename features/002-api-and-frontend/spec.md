# Spec — Feature 002: FastAPI layer & aligned frontend

> Checkpoint 3. Standard Gherkin over the 11 approved ACs in `acs.md`.
> AC-1..5 bind over HTTP; AC-6..11 bind to a real browser (Playwright) — both
> against the API in mocked-data mode (the retained, opt-in fixture mode), so
> every run is deterministic and LLM-free. Each scenario is tagged with its AC.

Feature: FastAPI layer & aligned frontend
  The analyst backend is reachable over HTTP with domain-true wire shapes, and
  the design-prototype frontend renders profiling, catalog, ingestion and
  provisional Q&A against it.

## API contract (HTTP)

  # AC-1
  Scenario: Datasets are served with their profiles and catalog
    Given the analyst service is running with mocked data
    When a client lists the datasets
    Then the datasets "sales", "customers" and "products" are returned
    And each dataset carries its column profiles and catalog descriptions

  # AC-2
  Scenario: The service reports that mocked data is active
    Given the analyst service is running with mocked data
    When a client checks the service health
    Then the service reports that mocked data is in use

  # AC-3
  Scenario: A dataset can be refreshed and deleted over the API
    Given the analyst service is running with mocked data
    When a client refreshes "sales" with a conforming file
    Then the refresh is accepted as a new version
    When a client deletes the dataset "customers"
    Then "customers" is no longer listed

  # AC-4
  Scenario: Requesting an unknown dataset yields a clear not-found error
    Given the analyst service is running with mocked data
    When a client requests the dataset "nope"
    Then the service answers not-found, naming "nope"

  # AC-5
  Scenario: An unambiguous question is answered directly with a trust trail
    Given the analyst service is running with mocked data
    When a client asks "What is the average order value?"
    Then an answer is returned with a summary and a trust trail

  # AC-12 — defect regression (exploratory 2026-07-02: empty uploads 500'd)
  Scenario: An invalid file is rejected cleanly over the API
    Given the analyst service is running with mocked data
    When a client ingests an empty file
    Then the ingestion is rejected as a client error with a clear message
    And no server error occurs

## Frontend flows (browser)

  # AC-6
  Scenario: The workspace lists the seeded datasets
    Given the analyst app is open in a browser
    Then the semantic catalog lists "sales", "customers" and "products"

  # AC-7
  Scenario: A dataset's profile and catalog descriptions are revealable
    Given the analyst app is open in a browser
    Then the table details describe the dataset "sales" in plain English
    And the table details show the row count "143,209 rows"
    And the columns are described in plain English with their roles

  # AC-8
  Scenario: An ambiguous question is clarified before it is answered
    Given the analyst app is open in a browser
    When the user asks "What is the revenue by region?"
    Then the agent asks which region column to use
    When the user chooses the customer region option
    Then an answer appears summarising revenue by region
    And the trust trail reveals assumptions, lineage and SQL

  # AC-8
  Scenario: A result can be viewed as a table, saved and exported
    Given the analyst app is open in a browser
    When the user asks "What is the revenue by region?"
    And the user chooses the customer region option
    And the user switches the answer to the table view
    Then the result table is shown with a CSV download
    When the user opens the save-as-dataset dialog
    Then an empty name is rejected
    When the user confirms a valid dataset name
    Then the result is confirmed saved to Ingest & Profile

  # AC-9
  Scenario: Uploading a file shows ingestion progressing to completion
    Given the analyst app is open on the ingestion view
    When the user drops a file on the upload zone
    Then the upload progresses to completion
    And "transactions" appears among the ingested datasets

  # AC-10
  Scenario: The user can move between the ingestion and workspace views
    Given the analyst app is open in a browser
    When the user opens the ingestion view
    Then the upload zone invites them to drop a file
    When the user opens the workspace view
    Then the Q&A panel invites them to ask a question

  # AC-11
  Scenario: A dataset can be deleted from the workspace
    Given the analyst app is open in a browser
    When the user deletes the dataset "sales"
    Then "sales.csv" no longer appears in the semantic catalog

  # AC-13 — defect regression (exploratory 2026-07-02: silent failed uploads)
  Scenario: A rejected upload is shown as failed with its reason
    Given the analyst app is open on the ingestion view
    When the user uploads an empty file
    Then the upload is marked failed
    And the failure reason mentions the file is empty
