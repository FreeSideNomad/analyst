# Spec — Feature 011: Encrypted-at-rest credentials

> Checkpoint 3. Standard Gherkin over the 12 approved ACs. Scenarios bind over
> the in-process seam (workspace repository + database manager + a synthetic
> SQLite database whose connection spec carries a username/password, so the
> secret's lifecycle is observable offline). "The service restarts" rebuilds
> the workspace over the same data directory. The read-only-guidance scenario
> (AC-12) binds to the shipped connect form's content. Each scenario is
> tagged (# AC-n).

Feature: Encrypted-at-rest credentials with seamless reconnect
  A connected database's credentials are remembered — sealed under an
  operator-supplied key that never touches the workspace store — so a restart
  reconnects automatically, and every failure of key or ciphertext fails safe
  to re-entry, never to plaintext.

## Seamless reconnect

  # AC-1
  Scenario: Connecting with the key configured remembers the connection
    Given the operator key is configured
    When a database is connected with credentials
    Then the connection is remembered for the next session

  # AC-2
  Scenario: A restart brings the connection back without re-entry
    Given the operator key is configured
    And a database is connected with credentials
    When the service restarts
    Then the database is connected again without re-entering credentials
    And its tables are queryable
    And its tables show their previously derived descriptions immediately

  # AC-3
  Scenario: The key can be supplied as a secret file
    Given the operator key is configured as a secret file
    And a database is connected with credentials
    When the service restarts
    Then the database is connected again without re-entering credentials

  # AC-3
  Scenario: The key can be supplied through the environment
    Given the operator key is configured through the environment
    And a database is connected with credentials
    When the service restarts
    Then the database is connected again without re-entering credentials

  # AC-3
  Scenario: The key never rests with the remembered connection
    Given the operator key is configured
    When a database is connected with credentials
    Then the workspace store contains no trace of the operator key

## Degraded states

  # AC-4
  Scenario: An unreachable database stays visible and retryable after a restart
    Given the operator key is configured
    And a database is connected with credentials
    And the database becomes unreachable while the service is down
    When the service restarts
    Then the connection is listed as unreachable
    And it still shows its previously derived descriptions
    When the database becomes reachable again and the user retries the connection
    Then the database is connected again without re-entering credentials

  # AC-5
  Scenario: Detaching forgets the stored credentials
    Given the operator key is configured
    And a database is connected with credentials
    When the user detaches the connection
    And the service restarts
    Then the connection does not reappear

  # AC-6
  Scenario: Without a key nothing persists and nothing breaks
    Given no operator key is configured
    When a database is connected with credentials
    Then the connection works for the session
    And nothing about the connection is persisted
    When the service restarts
    Then the connection does not reappear

## Failing safe

  # AC-7
  Scenario: A changed key means re-entry, never plaintext
    Given the operator key is configured
    And a database is connected with credentials
    When the service restarts with a different operator key
    Then the connection does not reappear
    And the service is working normally

  # AC-7
  Scenario: A removed key means re-entry, never plaintext
    Given the operator key is configured
    And a database is connected with credentials
    When the service restarts with no operator key
    Then the connection does not reappear
    And the service is working normally

  # AC-8
  Scenario: The data at rest yields no secret
    Given the operator key is configured
    When a database is connected with credentials
    Then no file in the workspace store contains the password

  # AC-9
  Scenario: Tampered credentials are rejected, not decrypted
    Given the operator key is configured
    And a database is connected with credentials
    And the stored credential record is tampered with
    When the service restarts
    Then the connection does not reappear
    And the service is working normally

  # AC-10
  Scenario: Reconnect keeps secrets off the wire and out of the logs
    Given the operator key is configured
    And a database is connected with credentials
    When the service restarts
    Then no listed connection carries a password
    And no listed connection reveals its sealed credentials
    And the reconnect activity log contains no password

## Cross-cutting

  # AC-11
  Scenario: Reconnect respects workspace isolation
    Given the operator key is configured
    And a database is connected with credentials in workspace "alpha"
    When the service restarts
    Then workspace "alpha" has the connection again
    And workspace "beta" does not see it

  # AC-12
  Scenario: The connect form recommends a read-only account
    Then the connection form offers guidance to use a read-only database account
