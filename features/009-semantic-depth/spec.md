# Spec — Feature 009: Semantic depth

> Checkpoint 3. Standard Gherkin over the 16 approved ACs. Backend discovery /
> validation / cataloguing scenarios bind over the in-process seam and HTTP
> against a real-store service; focus + async-progress flows bind to Playwright
> (`acceptance/e2e_009.py`, on `e2e_base`). Each scenario is tagged (# AC-n).

Feature: Semantic depth — PK/FK discovery + richer catalog to UI & planner
  Discovered relationships and data-grounded descriptions give the catalog real
  meaning, surfaced on focus and fed to the query planner.

## Relationship discovery & validation (backend)

  # AC-1
  Scenario: Declared keys from a database are surfaced
    Given a database with a declared foreign key from "rental.customer_id" to "customer.customer_id"
    When the database is connected and profiled
    Then the table "rental" carries a declared relationship to "customer" on "customer_id"

  # AC-2
  Scenario: An implied single-column foreign key is discovered
    Given a file "orders.csv" with a column "customer_id"
    And a file "customers.csv" whose key column "id" contains every "orders.customer_id" value
    When relationships are discovered
    Then an inferred relationship from "orders.customer_id" to "customers.id" is proposed

  # AC-3
  Scenario: A candidate that violates referential integrity is rejected
    Given a file "orders.csv" with a column "customer_id" containing a value absent from "customers.id"
    When relationships are discovered
    Then no relationship from "orders.customer_id" to "customers.id" is proposed

  # AC-4
  Scenario: A nullable foreign key is recorded as an optional relationship
    Given a file "orders.csv" whose "customer_id" has nulls and otherwise all match "customers.id"
    When relationships are discovered
    Then the relationship from "orders.customer_id" to "customers.id" is marked optional

  # AC-4
  Scenario: A fully-populated foreign key is recorded as a required relationship
    Given a file "orders.csv" whose "customer_id" has no nulls and all match "customers.id"
    When relationships are discovered
    Then the relationship from "orders.customer_id" to "customers.id" is marked required

  # AC-5
  Scenario: An inferred relationship records its evidence
    Given a file "orders.csv" whose "customer_id" all match "customers.id"
    When relationships are discovered
    Then the relationship from "orders.customer_id" to "customers.id" is marked inferred with full match coverage

  # AC-6
  Scenario: A relationship is discovered across a file and a connected database
    Given a connected database table "customer" keyed by "customer_id"
    And a file "orders.csv" whose "customer_id" all match "customer.customer_id"
    When relationships are discovered
    Then an inferred relationship from "orders.customer_id" to the database table "customer" is proposed

  # AC-7
  Scenario: Columns sharing a name but not their values are not linked
    Given a file "products.csv" with a column "id" and a file "regions.csv" with a column "id" whose values do not overlap
    When relationships are discovered
    Then no relationship between "products.id" and "regions.id" is proposed

## Richer meaning (catalog)

  # AC-8
  Scenario: A column description is grounded in its name and data
    Given a connected database table "address" with a column "district"
    When the table is catalogued
    Then the description of "district" is specific to its values and not "Text column from the source table"

  # AC-9
  Scenario: A table description aggregates its columns and relationships
    Given a file "orders.csv" related to "customers.csv" and "products.csv"
    When the table is catalogued
    Then the description of "orders" references its relationships to "customers" and "products"

## Real, automatic, async DB cataloguing

  # AC-10
  Scenario: Connecting a database catalogues its tables for real
    Given the app is open on the Ingest & Profile view
    When the user connects the fixture database "sales_db"
    And cataloguing completes
    Then the table "sales_db.Album" shows a real semantic description

  # AC-11
  Scenario: Cataloguing runs in the background with progress and refreshes when done
    Given the app is open on the Ingest & Profile view
    When the user connects the fixture database "sales_db"
    Then the connection appears immediately with its tables marked as cataloguing
    And each table refreshes to its semantic description without a manual reload

## Surface on focus (browser)

  # AC-12
  Scenario: Focusing a table shows its meaning and relationships
    Given the app is open on the Ingest & Profile view with related tables
    When the user selects the table "sales"
    Then its description is shown
    And its relationships to "customers" and "products" are listed with declared-or-inferred and required-or-optional

  # AC-13
  Scenario: Focusing a column shows its meaning, role, and relationship
    Given the app is open on the Ingest & Profile view with related tables
    When the user selects the column "customer_id" of "sales"
    Then its description and role are shown
    And it shows a relationship referencing "customers"

## Feed the planner

  # AC-14
  Scenario: A file question joins on a discovered relationship
    Given files "orders.csv" and "customers.csv" with a discovered relationship on "customer_id"
    When the user asks a question that needs both tables
    Then the answer's SQL joins them on the discovered relationship
    And the join keeps unmatched rows when the relationship is optional

## Cross-cutting

  # AC-15
  Scenario: Relationship discovery keeps bulk data local
    Given files "orders.csv" and "customers.csv"
    When relationships are discovered
    Then the referential-integrity check runs locally
    And only schema, profiles, and capped samples are sent to the language model

  # AC-16
  Scenario: Relationships and descriptions survive a restart
    Given a workspace with discovered relationships and catalogued tables
    When the service restarts
    Then the relationships and descriptions are still present

  # AC-16
  Scenario: A cataloguing failure for one table does not break the others
    Given a connected database where cataloguing fails for one table
    When cataloguing runs
    Then the failed table shows a not-yet-catalogued state
    And the other tables are catalogued normally
