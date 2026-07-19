# Spec — Feature 012: Guided predictive models (MVP)

> Checkpoint 3. Standard Gherkin over the 14 approved ACs. Realistic-data
> scenarios run against the REAL Ames dataset (downloaded on demand into
> the local test cache, never committed; pinned snapshot, fixed seeds).
> Agent turns replay a recorded cassette. The container scenario drives the
> BUILT DOCKER IMAGE end to end (browser + replay mode) — the owner's
> autonomy condition. Each scenario is tagged with its AC.

Feature: Guided predictive models
  A person who writes no code trains a trustworthy model through a guided
  conversation: real data arrives on demand, the task and features are
  decisions (not code), training is local and deterministic, evaluation is
  honest against real thresholds, and predictions become ordinary datasets.

## The gallery (realistic data, on demand)

  # AC-1
  Scenario: The Ames dataset arrives through the normal pipeline
    Given the sample gallery is available
    When the user adds the Ames house-price dataset
    Then a dataset of 1460 homes with 81 columns is profiled and queryable
    And adding it again uses the local cache without downloading

## Defining a model (recorded agent turns)

  # AC-2
  Scenario: A prediction task is defined as decisions, not code
    Given the Ames dataset is in the workspace
    When the user starts a new model to predict "SalePrice"
    Then a regression task is saved with a held-out fifth of the homes
    And the split was presented as a decision in plain language

  # AC-3
  Scenario: Features are proposed with reasons and user-curated
    Given the Ames dataset is in the workspace
    When the user starts a new model to predict "SalePrice"
    Then the agent proposes features each with a plain-language reason
    When the user removes one proposed feature and accepts the rest
    Then the accepted features materialize as a queryable feature table

  # AC-12
  Scenario: Model definition keeps bulk data local
    Given the Ames dataset is in the workspace
    When the user starts a new model to predict "SalePrice"
    Then the exchange sent for guidance carries schema and catalog metadata
    And the exchange carries no home records

  # AC-14
  Scenario: A failed guidance turn creates nothing
    Given the Ames dataset is in the workspace
    And the guidance will fail on the next attempt
    When the user starts a new model to predict "SalePrice"
    Then the failure is reported plainly
    And no task and no model exist afterwards

## Training and honest evaluation (real data, deterministic)

  # AC-4
  Scenario: Training is deterministic
    Given a defined SalePrice task with accepted features
    When the model is trained twice
    Then both runs report identical metrics

  # AC-5
  Scenario: Evaluation meets the real-data thresholds
    Given a defined SalePrice task with accepted features
    When the model is trained
    Then the upgraded model's holdout fit is at least 0.80
    And the upgraded model beats the simple baseline
    And the evaluation says in dollars how far off a typical prediction is

  # AC-6
  Scenario: The target can never leak into the features
    Given a defined SalePrice task with accepted features
    When the user tries to add "SalePrice" itself as a feature
    Then the addition is rejected with an explanation
    And the held-out homes never influenced training

  # AC-10
  Scenario: Parameters are bounded and optional
    Given a defined SalePrice task with accepted features
    When the model is trained with default parameters
    Then training succeeds without any parameter being touched
    When a parameter outside its allowed bounds is submitted
    Then the submission is rejected with the allowed range

## Predictions, registry, persistence

  # AC-7
  Scenario: Predictions become an ordinary dataset
    Given a trained SalePrice model
    Then a predictions dataset exists with one row per home
    And each row carries the actual price, the predicted price and the model version
    And the predictions dataset is queryable like any other

  # AC-8
  Scenario: The registry tells the model's story
    Given a trained SalePrice model
    Then the registry lists its data, features, split, seed and metrics
    And the most influential features are named in plain language

  # AC-9
  Scenario: Models and predictions survive a restart
    Given a trained SalePrice model
    When the app restarts
    Then the registry still lists the model with its metrics
    And the predictions dataset is still queryable

  # AC-11
  Scenario: Offline, existing models work and new ones say why not
    Given a trained SalePrice model
    And the app runs offline with no AI features available
    Then the registry and the predictions dataset still work
    And starting a new model fails with a plain message

  # AC-14
  Scenario: Model errors are clean
    Given a trained SalePrice model
    When the user opens a model that does not exist
    Then the action is rejected as not found
    When an empty feature selection is submitted
    Then it is rejected with a message

## The deployed container (the autonomy gate)

  # AC-13
  Scenario: The full journey passes against the deployed container
    Given the analyst container is built and running in replay mode
    When the user completes the model journey in a browser
    Then the predictions dataset is visible in the deployed app
    And the model's metrics are shown in its registry card
