# Spec — Feature 010: Workspace-aware cataloguing

> Checkpoint 3. Standard Gherkin over the 11 approved ACs. All scenarios bind
> over the in-process seam with synthetic CSV fixtures and small synthetic
> SQLite databases where a connected database is needed. The LLM path binds via
> cassette; the offline path is deterministic by construction. Each scenario is
> tagged (# AC-n). Note: a query result saved as a dataset re-enters through
> the ingest path, so the file-ingestion scenarios cover that trigger too.

Feature: Workspace-aware cataloguing
  A table's meaning is derived knowing the rest of the workspace — the other
  tables' meanings and the relationship graph — instead of in isolation, and
  that meaning stays coherent and persistent as the workspace grows.

## Cataloguing in the context of the workspace

  # AC-1
  Scenario: A new table is catalogued knowing the rest of the workspace
    Given a workspace with a catalogued file "customers.csv" keyed by "id"
    When a file "orders.csv" whose "customer_id" values all match "customers.id" is ingested
    Then the cataloguing context for "orders" names the table "customers" with its description
    And the cataloguing context for "orders" includes the columns of "customers"
    And the cataloguing context for "orders" includes the relationship between "orders" and "customers"

  # AC-1
  Scenario: The context carries columns only for directly-related tables
    Given a workspace with catalogued files "customers.csv" keyed by "id" and "products.csv" keyed by "sku"
    When a file "orders.csv" whose "customer_id" values all match "customers.id" is ingested
    Then the cataloguing context for "orders" names the table "products" with its description
    And the cataloguing context for "orders" does not include the columns of "products"

  # AC-2
  Scenario: A foreign-key column is described in terms of the table it references
    Given a workspace with a catalogued file "customers.csv" keyed by "id"
    When a file "orders.csv" whose "customer_id" values all match "customers.id" is ingested
    Then the description of column "customer_id" of "orders" references the meaning of "customers"

  # AC-2
  Scenario: A table's description situates it among the tables it links to
    Given a workspace with a catalogued file "customers.csv" keyed by "id"
    When a file "orders.csv" whose "customer_id" values all match "customers.id" is ingested
    Then the description of "orders" references "customers"

  # AC-3
  Scenario: The default offline cataloguer uses the workspace context
    Given a workspace with a catalogued file "customers.csv" keyed by "id"
    When a file "orders.csv" whose "customer_id" values all match "customers.id" is ingested with the offline cataloguer
    Then the description of "orders" references "customers"

  # AC-3
  Scenario: The language-model cataloguer uses the workspace context
    Given a workspace with a catalogued file "customers.csv" keyed by "id"
    When a file "orders.csv" whose "customer_id" values all match "customers.id" is ingested with the language-model cataloguer
    Then the description of "orders" references "customers"

  # AC-1
  Scenario: A connected database is catalogued knowing the workspace files
    Given a workspace with a catalogued file "orders.csv" with a column "customer_id"
    When a database whose table "customers" is keyed by "customer_id" is connected
    Then the cataloguing context for "customers" names the table "orders" with its description

  # AC-11
  Scenario: The workspace context is available in a fresh session
    Given a workspace with a catalogued file "customers.csv" keyed by "id"
    And the service restarts
    When a file "orders.csv" whose "customer_id" values all match "customers.id" is ingested
    Then the description of "orders" references "customers"

## Keeping the workspace coherent (retroactive)

  # AC-4
  Scenario: A new relationship re-catalogues the existing table it affects
    Given a workspace with a catalogued file "customers.csv" keyed by "id"
    When a file "orders.csv" whose "customer_id" values all match "customers.id" is ingested
    Then the description of "customers" states it is referenced by "orders"

  # AC-4
  Scenario: Connecting a database re-catalogues the existing file it links to
    Given a workspace with a catalogued file "orders.csv" with a column "customer_id"
    When a database whose table "customers" is keyed by "customer_id" is connected
    Then the description of "orders" states it references "customers"

  # AC-5
  Scenario: Re-cataloguing touches only the tables the new relationship affects
    Given a workspace with catalogued files "customers.csv" keyed by "id" and "products.csv" keyed by "sku"
    When a file "orders.csv" whose "customer_id" values all match "customers.id" is ingested
    Then the description of "customers" reflects its new relationship to "orders"
    And the catalog entry of "products" is unchanged from before the ingestion

## Persistence across sessions (connected databases)

  # AC-6
  Scenario: A connected database's catalog persists
    Given a connected database whose tables are catalogued
    When the service restarts
    Then each table of the connected database still has its description after the restart

  # AC-7
  Scenario: Reconnecting reuses the persisted meaning
    Given a connected database whose tables are catalogued
    When the service restarts and the database is reconnected
    Then the tables immediately show the same descriptions they had before the restart

  # AC-7
  Scenario: A schema change on reconnect triggers re-cataloguing for that table
    Given a connected database whose tables are catalogued
    And the schema of one table changes while the service is down
    When the service restarts and the database is reconnected
    Then the changed table is re-catalogued
    And the unchanged tables keep their persisted descriptions

## Cross-cutting

  # AC-8
  Scenario: The workspace context carries only metadata
    Given a workspace with a catalogued file "customers.csv" keyed by "id"
    When a file "orders.csv" whose "customer_id" values all match "customers.id" is ingested
    Then the cataloguing context contains no data rows
    And the cataloguing context carries only names, descriptions, roles, and relationships

  # AC-9
  Scenario: Workspace-aware cataloguing stays deterministic offline
    Given a workspace with a catalogued file "customers.csv" keyed by "id"
    When a file "orders.csv" whose "customer_id" values all match "customers.id" is ingested twice into identical workspaces
    Then both runs derive identical descriptions for "orders"

  # AC-10
  Scenario: A re-cataloguing failure does not break ingestion
    Given a workspace with a catalogued file "customers.csv" keyed by "id"
    And re-cataloguing of existing tables is failing
    When a file "orders.csv" whose "customer_id" values all match "customers.id" is ingested
    Then the ingestion of "orders" succeeds
    And the description of "customers" remains its prior catalog entry

  # AC-10
  Scenario: A workspace-context failure degrades to cataloguing in isolation
    Given a workspace with a catalogued file "customers.csv" keyed by "id"
    And the workspace context cannot be built
    When a file "orders.csv" whose "customer_id" values all match "customers.id" is ingested
    Then the ingestion of "orders" succeeds
    And "orders" has a description derived without workspace context
