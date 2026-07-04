# Spec — Feature 005: Relational database federation

> Checkpoint 3. Standard Gherkin over the 11 approved ACs in `acs.md`.
> AC-1..8 bind over HTTP; AC-9..11 bind to a real browser (Playwright) — both
> against the API in fixtures mode with the bundled sample SQLite database, so
> every run is deterministic, offline and LLM-free. Each scenario is tagged
> with its AC.

Feature: Relational database federation
  A user connects a relational database and its tables become queryable,
  profiled, catalogued datasets through federation — queried in place, never
  bulk-copied.

## API contract (HTTP)

  # AC-1
  Scenario: Connecting a database exposes its tables as datasets
    Given the analyst service is running with mocked data
    And a sample relational database is available
    When a client connects the sample database as "chinook"
    Then the connection "chinook" is listed with its engine and tables
    And the tables "Album", "Artist" and "Track" appear among the datasets

  # AC-2
  Scenario: Connected tables are profiled and catalogued in place
    Given the analyst service is running with mocked data
    And a sample relational database is available
    When a client connects the sample database as "chinook"
    Then the dataset "chinook.Album" reports its row count and column profiles
    And the dataset "chinook.Album" carries a plain-English catalog entry

  # AC-3
  Scenario: Declared keys are read into the catalog
    Given the analyst service is running with mocked data
    And a sample relational database is available
    When a client connects the sample database as "chinook"
    Then the connection reports "AlbumId" as the primary key of "Album"
    And the connection reports that "Album" references "Artist"
    And the catalog describes "ArtistId" of "chinook.Album" as a declared foreign key

  # AC-4
  Scenario: Connection secrets are never returned by the service
    Given the analyst service is running with mocked data
    And a sample relational database is available
    When a client connects the sample database as "chinook" sending a password
    Then no connection response or listing reveals the password

  # AC-5
  Scenario: Detaching a connection removes its datasets
    Given the analyst service is running with mocked data
    And a sample relational database is available
    When a client connects the sample database as "chinook"
    And the client detaches the connection "chinook"
    Then the connection "chinook" is no longer listed
    And no "chinook" tables remain among the datasets

  # AC-6
  Scenario: Connecting to an unreachable database fails cleanly
    Given the analyst service is running with mocked data
    When a client connects to an unreachable PostgreSQL server
    Then the connection is rejected as a client error with a clear reason
    And no server error occurs

  # AC-7
  Scenario: A duplicate connection name is rejected
    Given the analyst service is running with mocked data
    And a sample relational database is available
    When a client connects the sample database as "chinook"
    And a client connects the sample database as "chinook"
    Then the second connection is rejected as already existing

  # AC-8
  Scenario: Detaching an unknown connection yields a clear not-found error
    Given the analyst service is running with mocked data
    When the client detaches the connection "nope"
    Then the detach is answered not-found, naming "nope"

## Frontend flows (browser)

  # AC-9
  Scenario: The user connects a database from the catalog tree
    Given the analyst app is open in a browser
    And a sample relational database is available
    When the user opens the database connection form
    And the user connects the sample database as "chinook" through the form
    Then "chinook" appears among the connected databases
    And the table "chinook.Album" appears in the semantic catalog

  # AC-10
  Scenario: The user detaches a connected database
    Given the analyst app is open in a browser
    And a sample relational database is available
    And the user has connected the sample database as "chinook" through the form
    When the user detaches the database "chinook"
    Then "chinook" no longer appears among the connected databases
    And the table "chinook.Album" no longer appears in the semantic catalog

  # AC-11
  Scenario: A failed connection shows its reason in the form
    Given the analyst app is open in a browser
    When the user opens the database connection form
    And the user submits an unreachable PostgreSQL connection
    Then the form shows that the connection failed with a reason
