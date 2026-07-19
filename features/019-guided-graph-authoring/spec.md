# Spec — Feature 019: Guided graph authoring

> Checkpoint 3. Standard Gherkin over the 12 approved ACs. The curated
> Berka data is the corpus, arriving the two ways a real user's data
> arrives: as a seeded demo Postgres connection and as ordinary file
> uploads. Equivalence scenarios assert the generated flow reproduces the
> shipped 018 curated reference (baseline ±0.03 of 0.7647, graph ±0.07 of
> 0.7182 on loan default, deterministic seeds). Agent authoring turns
> replay a recorded cassette. The container scenario drives the BUILT
> analyst:ml image with the demo database alongside — the owner's
> autonomy gate. Each scenario is tagged with its AC.

Feature: Guided graph authoring
  A UI-only user points the relational tier at THEIR data — a connected
  database or uploaded files — and trains the three-tier model through
  confirmed decisions: structure derived from validated links, outcomes
  named and hidden, honesty provable even where no reference exists.

## Arrival — the user's data, two ways

  # AC-1
  Scenario: Berka arrives as a connected relational database
    Given the demo database is seeded with the Berka tables
    When the user connects that database
    Then the connected tables are profiled and catalogued in place
    And the links between them are validated against the data

## Deriving structure and authoring the task

  # AC-2
  Scenario: The graph structure is derived from the workspace
    Given the Berka database is connected and catalogued
    When the user asks for a relational model on it
    Then the derived structure names the tables, links and time column in plain language
    And every link used is one the workspace has validated

  # AC-3
  Scenario: Task decisions are authored with guidance and confirmed
    Given the Berka database is connected and catalogued
    When the user asks to predict which loans will end in default
    Then the agent proposes the entity, outcome definition, prediction moment, cutoffs and hidden columns as plain-language decisions
    And nothing trains before the user confirms the decisions

  # AC-10
  Scenario: The agent sees decisions, never data
    Given the Berka database is connected and catalogued
    When the user asks to predict which loans will end in default
    Then the authoring exchange carries schema and catalog metadata only
    And the outcome definition runs locally under the read-only guard

## Equivalence — the generated flow against the curated reference

  # AC-4
  Scenario: The connected-database path reproduces the curated reference
    Given a confirmed loan default task authored on the connected Berka
    When the relational model is trained
    Then the baseline's held-out score is within 0.03 of the curated 0.7647
    And the graph's held-out score is within 0.07 of the curated 0.7182

  # AC-5
  Scenario: The uploaded-files path reproduces the curated reference
    Given the Berka tables are uploaded as files and catalogued
    And a confirmed loan default task authored on the uploads
    When the relational model is trained
    Then the baseline's held-out score is within 0.03 of the curated 0.7647
    And the graph's held-out score is within 0.07 of the curated 0.7182

## Honesty — structural, for any dataset

  # AC-6
  Scenario: Outcome columns cannot reach the model
    Given a confirmed loan default task authored on the connected Berka
    Then the columns the outcome definition reads are hidden automatically
    When the user asks to include a hidden outcome column
    Then the request is refused with the reason

  # AC-6
  Scenario: A column that gives the answer away is flagged
    Given a confirmed loan default task authored on the connected Berka
    When a remaining column alone nearly perfectly predicts the outcome
    Then the user is warned it likely records the outcome

  # AC-7
  Scenario: The wiring is provably honest without any reference
    Given a confirmed loan default task authored on the connected Berka
    When the model is trained on deliberately shuffled outcomes
    Then the held-out score is a coin flip
    And training again with the same seed reproduces the same result

## Guardrails, errors, disclosure

  # AC-8
  Scenario: Unsuitable data is refused with reasons
    Given a workspace whose tables have no validated links
    When the user asks for a relational model there
    Then the request is refused before training with the missing prerequisites named

  # AC-9
  Scenario: A failed authoring turn leaves nothing behind
    Given the Berka database is connected and catalogued
    And the authoring guidance will fail on the next attempt
    When the user asks to predict which loans will end in default
    Then the failure is reported plainly
    And no task and no model exist afterwards

  # AC-11
  Scenario: The registry discloses the source and the local build
    Given a trained model from the connected-database path
    Then the registry story names the connection the data came from
    And it states plainly that training used a temporary local copy that never left the machine

## The deployed container (the autonomy gate)

  # AC-12
  Scenario: The full journey passes against the deployed ML container
    Given the analyst ML container runs with the seeded demo database alongside
    When the user completes the guided authoring journey in a browser
    Then the trained model and its predictions are visible in the deployed app
    And the registry card tells the story including the data's source
