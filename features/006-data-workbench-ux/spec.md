# Spec — Feature 006: two-surface workbench UX

> Checkpoint 3. Standard Gherkin over the 12 approved ACs. UI flows bind to
> Playwright (`acceptance/e2e_006.py`, on `e2e_base`) against the fixtures API;
> the naming rule (AC-3) also binds to backend unit tests. Fixtures extend the
> seeded workspace with a multi-sheet Excel, a single CSV, and a (fixture)
> connected database so the grouping is exercised. Each scenario is tagged (# AC-n).

Feature: Two-surface workbench — Ingest & Profile (data + catalog) and Query (chat)
  Data is added and explored on one surface; asking questions is a separate,
  metadata-free surface.

## Dataset naming (backend)

  # AC-3
  Scenario: An Excel workbook is named by file and sheet
    Given a workspace with the seeded datasets
    When an Excel file "company.xlsx" with sheets "employees" and "departments" is ingested
    Then the datasets "company.employees.xlsx" and "company.departments.xlsx" exist
    And they share the group "company.xlsx"

  # AC-3
  Scenario: A single-table file is named by file and extension
    Given a workspace with the seeded datasets
    When a CSV file "orders.csv" is ingested
    Then the dataset "orders.csv" exists
    And its group is "orders.csv" with one table

## The workbench — Ingest & Profile (browser)

  # AC-1
  Scenario: A file can be uploaded from Ingest & Profile
    Given the app is open on the Ingest & Profile view
    Then the view invites the user to upload a file
    And the view offers to connect a database

  # AC-1
  Scenario: A database can be connected from Ingest & Profile
    Given the app is open on the Ingest & Profile view
    When the user connects the fixture database "sales_db"
    Then "sales_db" appears in the Databases section

  # AC-2
  Scenario: Sources are grouped into Files and Databases
    Given the app is open on the Ingest & Profile view with a connected database
    Then the left rail shows a "Files" section and a "Databases" section
    And each source can be expanded to its tables and each table to its columns

  # AC-4
  Scenario: A selected table shows its column profiles
    Given the app is open on the Ingest & Profile view
    When the user selects the table "sales"
    Then each column's inferred type and null rate are shown

  # AC-5
  Scenario: A selected table shows its semantic catalog
    Given the app is open on the Ingest & Profile view
    When the user selects the table "sales"
    Then the table's plain-English description is shown
    And each column's description and role are shown

  # AC-6
  Scenario: A column can be drilled into
    Given the app is open on the Ingest & Profile view
    When the user selects a column of "sales"
    Then the column drilldown shows its profile and its semantic description

  # AC-7
  Scenario: Connected-database tables are shown but marked not-yet-queryable
    Given the app is open on the Ingest & Profile view with a connected database
    When the user expands the database "sales_db"
    Then its tables are listed with profiles
    And they are marked as not yet answerable by Q&A

  # AC-8
  Scenario: A database can be disconnected
    Given the app is open on the Ingest & Profile view with a connected database
    When the user disconnects the database "sales_db"
    Then "sales_db" no longer appears in the Databases section

## The Query surface (browser)

  # AC-9
  Scenario: The Query tab is the conversation only
    Given the app is open in a browser
    When the user opens the Query view
    Then the Q&A conversation is shown
    And no catalog tree or metadata panel is shown

  # AC-10
  Scenario: File Q&A still answers with a trust trail
    Given the app is open on the Query view
    When the user asks "What is the revenue by region?"
    Then the agent asks which region column to use
    When the user chooses the customer region option
    Then an answer appears with its trust trail

## Cross-cutting

  # AC-11
  Scenario: The user can move between the two surfaces
    Given the app is open in a browser
    When the user opens the Ingest & Profile view
    Then the workbench is shown
    When the user opens the Query view
    Then the Q&A conversation is shown

  # AC-12 — amended by feature 016 (catalog curation, owner-approved
  # 2026-07-18): descriptions remain non-editable as raw text, but curation
  # affordances (answer a clarification, suggest a correction) now exist —
  # every change flows through the agent pipeline, never a direct edit.
  Scenario: The catalog is never directly editable
    Given the app is open on the Ingest & Profile view
    When the user selects the table "sales"
    Then the semantic descriptions are shown without a direct edit control
