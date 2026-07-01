# Spec — Feature 001: File ingestion & agentic data profiling

> Checkpoint 3. Standard Gherkin formalization of the 24 approved ACs in `acs.md`.
> External observables only — no implementation language. Scoped workspace-light (a single default workspace).
> Each scenario is tagged with the AC(s) it covers.

Feature: File ingestion & agentic data profiling
  A user adds a tabular file to a workspace and, on autopilot, gets a profiled,
  queryable dataset with an agent-authored semantic catalog entry.

## Happy path

  # AC-1, AC-2, AC-3
  Scenario: A clean CSV becomes a profiled, queryable dataset
    Given a clean CSV file "sales.csv" with a header row and 100 data rows
    When the user ingests the file
    Then a dataset named "sales" is available
    And the dataset has the same columns as the file
    And querying the dataset returns the same 100 rows as the file
    And the dataset reports a row count of 100
    And each column reports an inferred type, a null rate, a distinct-value count, and representative sample values

  # AC-2 (numeric profiling detail)
  Scenario: Numeric columns get distribution statistics
    Given a clean CSV file with a numeric column "amount"
    When the user ingests the file
    Then the profile for "amount" reports its minimum, maximum, and quantiles

  # AC-3 (durability)
  Scenario: An ingested dataset remains queryable after a restart
    Given the user has ingested a clean CSV file "sales.csv"
    When the system restarts
    Then the dataset "sales" is still available and returns the same rows

  # AC-4
  Scenario: An agent-authored catalog entry is produced automatically
    Given a clean CSV file describing customer orders
    When the user ingests the file
    Then a catalog entry for the dataset exists
    And the catalog entry has a plain-English description of the table
    And each column has a plain-English description and an inferred role
    And the user was not asked any questions

  # AC-5
  Scenario Outline: Rich scalar types are inferred per column
    Given a CSV column "<column>" whose values are <description>
    When the user ingests the file
    Then the inferred type of "<column>" is "<type>"

    Examples:
      | column     | description                          | type     |
      | note       | free-form text                       | text     |
      | quantity   | whole numbers                        | integer  |
      | price      | numbers with decimals                | decimal  |
      | active     | true/false values                    | boolean  |
      | order_date | calendar dates                       | date     |
      | created_at | dates with a time of day             | datetime |

  # AC-6
  Scenario: Each non-empty Excel sheet becomes its own dataset
    Given an Excel workbook with two non-empty sheets "orders" and "returns"
    When the user ingests the workbook
    Then a dataset "orders" is available
    And a dataset "returns" is available
    And each dataset is independently profiled and catalogued

  # AC-7 (TSV)
  Scenario: A tab-separated file is ingested like a CSV
    Given a clean tab-separated file "data.tsv" with a header row
    When the user ingests the file
    Then a profiled, queryable dataset "data" is available

  # AC-7 (JSON records)
  Scenario: A JSON array of records becomes a dataset
    Given a JSON file containing an array of 50 order records
    When the user ingests the file
    Then a dataset with 50 rows is available
    And each record field is a profiled column

  # AC-7 (nested JSON)
  Scenario: Deeply nested JSON values are recorded, not dropped
    Given a JSON file whose records contain a nested object under "shipping"
    When the user ingests the file
    Then the "shipping" content is preserved in the dataset
    And the profile records that "shipping" holds nested structure

  # AC-8
  Scenario: A clean file ingests end-to-end with no questions
    Given a clean, unambiguous CSV file
    When the user ingests the file
    Then ingestion completes successfully
    And the user was not asked any questions

## Edge cases

  # AC-9
  Scenario: A mixed-type column is widened to text and recorded as mixed
    Given a CSV column "code" whose values are mostly whole numbers with a few text values
    When the user ingests the file
    Then the inferred type of "code" is "text"
    And the profile records that "code" was mixed
    And the profile names the dominant type and shows example off-type values
    And ingestion completes successfully

  # AC-10
  Scenario: A headerless file gets synthesized column names
    Given a CSV file whose first row is data rather than column names
    When the user ingests the file
    Then the dataset columns are named "column_1", "column_2", and so on
    And no data row was consumed as a header
    And the profile records that column names were synthesized

  # AC-11 (header-only)
  Scenario: A header-only file becomes a zero-row dataset
    Given a CSV file with a header row but no data rows
    When the user ingests the file
    Then a dataset with 0 rows is available
    And the dataset's schema is fully profiled

  # AC-11 (truly empty)
  Scenario: An empty file is rejected with a clear message
    Given a file with no content
    When the user ingests the file
    Then ingestion is rejected with a clear, friendly message
    And no dataset is created

  # AC-12
  Scenario: Duplicate column names are automatically disambiguated
    Given a CSV file with two columns both named "total"
    When the user ingests the file
    Then the dataset has distinct column names "total" and "total_2"
    And the profile records that the source had duplicate column names

## Errors & security

  # AC-13
  Scenario Outline: Common non-UTF-8 encodings are auto-detected and decoded
    Given a CSV file encoded as <encoding>
    When the user ingests the file
    Then the text values are decoded correctly
    And the profile records a detected encoding

    Examples:
      | encoding |
      | UTF-16   |
      | latin-1  |
      | UTF-8-BOM|

  # AC-14
  Scenario: An unsupported file format is rejected clearly
    Given a file in an unsupported format
    When the user ingests the file
    Then ingestion is rejected with a message naming the supported formats CSV, TSV, Excel, and JSON
    And no dataset is created

  # AC-15
  Scenario: A malformed file fails cleanly
    Given a corrupt file that cannot be parsed
    When the user ingests the file
    Then ingestion fails with a clear, actionable error
    And no partial dataset remains

  # AC-16 — governance invariant (security-critical)
  Scenario: Only metadata and capped samples are sent to the AI model
    Given a CSV file with 100,000 rows
    When the user ingests the file
    Then the AI model receives only schema, profiles, and a capped number of small samples
    And the number of sample values sent is within the enforced cap
    And every AI model interaction is recorded in an egress log
    And no bulk row data appears in the egress log

  # AC-17
  Scenario: A failure during profiling leaves no partial dataset
    Given a file whose cataloguing fails partway through
    When the user ingests the file
    Then no dataset is left behind
    And the user sees a clear error and can retry

## Cross-cutting

  # AC-18 — refresh with schema validation and ask-to-loosen
  Scenario: Refreshing with conforming data replaces it in place
    Given an existing dataset "sales" with an established schema
    And a new file whose data conforms to that schema
    When the user refreshes "sales" with the new file
    Then the new data is validated against the schema before replacement
    And the dataset's data is replaced with the new data
    And the user was not asked any questions

  # AC-18 — non-conforming refresh asks to loosen
  Scenario: Refreshing with non-conforming data asks before proceeding
    Given an existing dataset "sales" with an established schema
    And a new file whose data violates that schema
    When the user refreshes "sales" with the new file
    Then the existing data is not silently replaced
    And the user is asked, with concrete options, whether to loosen the validations
    And the data is replaced only after the user chooses to loosen them

  # AC-19
  Scenario: A refresh creates a new, non-destructive version
    Given an existing dataset "sales"
    When the user refreshes it with new data that conforms
    Then a new version of "sales" is created
    And the prior version is retained
    And the catalog links the versions

  # AC-20
  Scenario: A dataset can be deleted cleanly
    Given an existing dataset "sales"
    When the user deletes it
    Then the dataset is no longer available
    And its data and its catalog entry are removed with no orphaned artifacts

  # AC-21 (within envelope)
  Scenario: A large file within the envelope is profiled responsively
    Given a CSV file of roughly 1 gigabyte with a few million rows
    When the user ingests the file
    Then the dataset is profiled and catalogued successfully

  # AC-21 (beyond envelope)
  Scenario: A file beyond the envelope is rejected with a clear message
    Given a file larger than the supported size
    When the user ingests the file
    Then ingestion is rejected with a clear "too large for this version" message

  # AC-22
  Scenario: The agent asks rather than guesses when confidence is very low
    Given a column the agent cannot confidently describe or assign a role to
    When the file is ingested
    Then the agent asks the user a question with concrete options
    And the agent does not fabricate a description for that column

  # AC-23
  Scenario Outline: Ingestion status is observable
    Given a file being ingested
    When ingestion reaches the "<state>" state
    Then the dataset's status observably reflects "<state>"

    Examples:
      | state       |
      | in progress |
      | complete    |
      | failed      |

  # AC-24 — validated by the golden corpus
  Scenario Outline: Profiling matches known ground truth on real-world datasets
    Given the golden-corpus dataset "<dataset>" with documented ground truth
    When the user ingests it
    Then the reported types, null rates, and cardinalities match the documented ground truth within tolerance

    Examples:
      | dataset       |
      | titanic       |
      | messy_imdb    |
      | messy_hr      |
      | superstore    |
