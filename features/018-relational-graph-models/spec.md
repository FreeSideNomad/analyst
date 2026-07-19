# Spec — Feature 018: Relational graph (GNN) models

> Checkpoint 3. Standard Gherkin over the 14 approved ACs. Reference-data
> scenarios run against the REAL Berka dataset (downloaded on demand from
> public mirrors into the local test cache, never committed; pinned
> snapshot, fixed seeds) and assert each tier against ITS OWN number from
> the paper's RESULTS.md, within ±0.03. The fast board validates the
> loan_default task end to end; the full three-task reference matrix is
> the ML_FULL suite (run before shipping and on the nightly gate, like
> E2E gating). The container scenario drives the BUILT analyst:ml IMAGE —
> the owner's autonomy gate. Each scenario is tagged with its AC.

Feature: Relational graph models
  The Models area learns from linked tables, not just flat ones: a graph
  tier validated by reproducing the owner's paper on real banking data,
  an honest baseline, a hybrid, and the same registry, predictions, and
  plain-language story as every other model.

## The reference bundle (real relational data, on demand)

  # AC-1
  Scenario: The Berka bundle arrives through the normal pipeline
    Given the sample gallery is available
    When the user adds the Berka banking dataset
    Then the Berka tables are profiled and queryable with their links validated
    And adding Berka again uses the local cache without downloading

## Defining a relational task (decisions, not code)

  # AC-2
  Scenario: A relational task is framed in plain language with temporal honesty
    Given the Berka bundle is in the workspace
    When the user starts the loan default prediction task
    Then the task is framed as a decision in plain language
    And the columns that record the outcome are named and excluded

  # AC-11
  Scenario: An unsuitable workspace is refused with a reason
    Given a workspace whose tables have no validated links
    When the user asks for a relational model there
    Then the request is refused before training with the missing prerequisites named

  # AC-13
  Scenario: Task guidance carries no records
    Given the Berka bundle is in the workspace
    When the user starts the loan default prediction task
    Then any guidance exchange carries schema and catalog metadata only
    And the exchange carries no account, transaction or client records

## Training and reference validation (the code-validity gate)

  # AC-3
  Scenario: Graph training is deterministic
    Given the loan default task is defined
    When the graph model is trained twice with the same seed
    Then both runs report identical evaluation scores

  # AC-4, AC-5
  Scenario: Both tiers reproduce the paper on loan default
    Given the loan default task is defined
    When the graph model and the baseline are trained
    Then the graph model's held-out score is within 0.03 of the paper's 0.7182
    And the baseline's held-out score is within 0.03 of the paper's 0.7647
    And the comparison between tiers is reported truthfully

  # AC-4, AC-5 (full matrix — ML_FULL suite)
  Scenario Outline: The full reference matrix reproduces the paper
    Given the Berka task "<task>" is defined
    When the graph model and the baseline are trained for "<task>"
    Then the graph model's held-out score is within 0.03 of "<graph_auroc>"
    And the baseline's held-out score is within 0.03 of "<baseline_auroc>"

    Examples:
      | task           | graph_auroc | baseline_auroc |
      | account_churn  | 0.7592      | 0.9018         |
      | card_adoption  | 0.6787      | 0.7999         |

  # AC-6
  Scenario: The hybrid tier is trained and honestly compared
    Given the loan default task is defined
    When the hybrid model is trained on the same split
    Then the hybrid's held-out score is reported alongside both parents
    And the hybrid scores no more than 0.05 below the stronger parent

  # AC-12
  Scenario: A failed training run leaves nothing behind
    Given the loan default task is defined
    And training will fail partway through
    When the graph model is trained
    Then the failure is reported plainly
    And the registry contains no partial model

## Predictions, registry, persistence

  # AC-7
  Scenario: Relational predictions become an ordinary dataset
    Given a trained loan default model
    Then a predictions dataset exists with one row per loan
    And each row carries the actual outcome, the predicted likelihood and the holdout flag
    And the predictions dataset is queryable like any other

  # AC-8
  Scenario: The registry tells the relational story
    Given a trained loan default model
    Then the registry names the task, the tables and links learned from, the time split, the seed and the set sizes
    And every tier's score is stated in plain language

  # AC-9
  Scenario: Relational models survive a restart
    Given a trained loan default model
    When the app restarts
    Then the registry still lists the relational model with its story
    And the predictions dataset is still queryable

## The lean image and the ML variant

  # AC-10
  Scenario: Without the ML runtime the tier degrades honestly
    Given the app runs without the ML runtime
    Then the relational tier explains plainly that the ML variant is needed
    And single-table models keep working

  # AC-14
  Scenario: The full journey passes against the deployed ML container
    Given the analyst ML container is built and running in replay mode
    When the user completes the relational model journey in a browser
    Then the loan predictions dataset is visible in the deployed app
    And the relational model's story is shown in its registry card
