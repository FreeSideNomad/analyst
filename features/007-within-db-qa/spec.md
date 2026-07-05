# Spec — Feature 007: within-DB Q&A (phase 2)

> Checkpoint 3. The execution core, bound deterministically over the in-process
> seam (`StoreRepository` + `DatabaseManager`) against the Chinook golden SQLite
> — no live model. Each scenario is tagged (# AC-n).

Feature: Within-DB Q&A — connected-database tables become queryable
  A connected scanner database's tables run planner SQL against the source,
  read-only, with the same governance as file Q&A.

  # AC-1
  Scenario: A connected database's tables become queryable
    Given a workspace with the connected database "sales_db"
    Then the table "sales_db.Album" is marked queryable

  # AC-2
  Scenario: The planner is offered the connected tables
    Given a workspace with the connected database "sales_db"
    Then the planner's table set includes "sales_db.Album"

  # AC-3
  Scenario: Planner SQL runs against a connected table
    Given a workspace with the connected database "sales_db"
    When the query 'SELECT COUNT(*) AS n FROM "sales_db.Album"' is executed
    Then a non-empty result is returned

  # AC-3
  Scenario: A join across two connected tables runs
    Given a workspace with the connected database "sales_db"
    When the query 'SELECT COUNT(*) AS n FROM "sales_db.Album" a JOIN "sales_db.Artist" r ON a.ArtistId = r.ArtistId' is executed
    Then a non-empty result is returned

  # AC-4
  Scenario: Disconnecting removes queryability
    Given a workspace with the connected database "sales_db"
    When the database "sales_db" is disconnected
    Then the query 'SELECT COUNT(*) FROM "sales_db.Album"' can no longer run
