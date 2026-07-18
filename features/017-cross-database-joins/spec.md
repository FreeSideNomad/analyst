# Spec — Feature 017: Cross-database joins

> Checkpoint 3. Standard Gherkin over the 9 approved ACs. Scenarios bind
> over the in-process seam with two synthetic SQLite connections; the NL
> planning turn replays a recorded cassette. Each scenario is tagged with
> its AC.

Feature: Cross-database joins
  One plain-English question joins tables from two different connected
  databases; the join runs locally, the trail names both systems, and the
  cross-database key is discovered, not declared.

  # AC-3
  Scenario: The cross-database key is discovered
    Given a connected CRM database and a connected billing database
    When relationships are discovered across the workspace
    Then a relationship links billing invoices to CRM customers

  # AC-1 + AC-2
  Scenario: A question spanning both databases is answered with the join disclosed
    Given a connected CRM database and a connected billing database
    When the user asks which customer segment generates the most revenue
    Then the answer shows "enterprise" leading at 150
    And the answer's query names both the CRM and billing tables

  # AC-4
  Scenario: The join executes locally and keeps bulk data local
    Given a connected CRM database and a connected billing database
    When the user asks which customer segment generates the most revenue
    Then the planning exchange carries only table metadata
    And the exchange carries no customer or invoice rows

  # AC-5
  Scenario: Restart with remembered credentials keeps the question answerable
    Given a connected CRM database and a connected billing database
    And an operator key is configured
    When the app restarts over the same data
    Then asking the segment question again shows "enterprise" leading at 150

  # AC-6
  Scenario: A question needing a detached database fails safe
    Given a connected CRM database and a connected billing database
    When the billing database is disconnected
    And the user asks which customer segment generates the most revenue
    Then the service abstains or reports plainly
    And no answer is fabricated

  # AC-7
  Scenario: A single-database question is unchanged
    Given a connected CRM database and a connected billing database
    When the user asks how many customers there are
    Then the answer is 3 from the CRM database alone

  # AC-8
  Scenario: The sample kit is deterministic
    Given the synthetic sample databases are generated twice
    Then both runs produce identical databases
    And the documented totals hold: enterprise 150, smb 50

  # AC-9
  Scenario: Asking before any database is connected stays clean
    Given no database is connected
    When the user asks which customer segment generates the most revenue
    Then the service abstains with a plain explanation
