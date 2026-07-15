# Spec — Feature 013: Data normalization detection

> Checkpoint 3. Standard Gherkin over the 12 approved ACs in `acs.md`.
> Detection/apply/revoke scenarios bind over the in-process seam (a real
> store in the scenario tmp_path); the workbench flow (AC-11) binds to a
> real browser against the fixtures app. Fully deterministic — detection is
> local and rule application never calls a model. Each scenario is tagged
> with its AC.

Feature: Data normalization detection
  Ingested data with inconsistent value representations (case variants,
  stray whitespace) is detected at profiling time; the app proposes explicit
  rules the user approves or rejects — never silently applied — and approved
  rules standardize what queries see while the original data stays intact
  and recoverable.

## Detection (in-process)

  # AC-1
  Scenario: Case variants of the same value are detected
    Given an ingested file whose "region" column holds "East", "east", "EAST", "West" and "West"
    When the user reviews the dataset's normalization findings
    Then a finding for column "region" groups the case variants "East", "east" and "EAST"
    And each variant in the finding carries its row count

  # AC-2
  Scenario: Whitespace inconsistencies are detected
    Given an ingested file whose "city" column holds "New York", " New York", "New  York" and "Boston"
    When the user reviews the dataset's normalization findings
    Then a finding for column "city" groups the whitespace variants of "New York"

  # AC-3
  Scenario: Clean columns produce no proposals
    Given an ingested file whose "region" column holds "East", "East" and "West"
    When the user reviews the dataset's normalization findings
    Then no normalization is proposed

  # AC-4
  Scenario: A proposal is an explicit plain-language rule
    Given an ingested file whose "region" column holds "East", "east", "EAST", "West" and "West"
    When the user reviews the dataset's normalization findings
    Then the proposal for column "region" describes merging 3 variants into "East"

  # AC-12
  Scenario: Detection runs without any model calls
    Given the app runs offline with no AI features available
    And an ingested file whose "region" column holds "East", "east", "EAST", "West" and "West"
    When the user reviews the dataset's normalization findings
    Then a finding for column "region" groups the case variants "East", "east" and "EAST"

  # AC-12
  Scenario: Identifier-like columns are exempt from detection
    Given an ingested file where near-unique "order_id" values include the case-colliding pair "A1" and "a1"
    When the user reviews the dataset's normalization findings
    Then no proposal targets column "order_id"

## Applying, revoking, rejecting (in-process)

  # AC-5
  Scenario: Pending proposals never change what queries see
    Given an ingested file whose "region" column holds "East", "east", "EAST", "West" and "West"
    When the user queries the distinct values of "region" without approving anything
    Then the values "East", "east", "EAST" and "West" appear exactly as ingested

  # AC-6
  Scenario: Approving a rule standardizes what queries see
    Given an ingested sales file where case variants of "East" carry amounts 10, 20 and 30 and "West" carries 40
    When the user approves the proposed rule for column "region"
    And the user asks for the total amount by region
    Then the totals show "East" at 60 and "West" at 40

  # AC-7
  Scenario: Revoking an approved rule restores the original values
    Given an ingested sales file where case variants of "East" carry amounts 10, 20 and 30 and "West" carries 40
    And the proposed rule for column "region" is approved
    When the user revokes the approved rule for column "region"
    Then the distinct values of "region" are "East", "east", "EAST" and "West" again

  # AC-8
  Scenario: A dismissed proposal stays dismissed
    Given an ingested file whose "region" column holds "East", "east", "EAST", "West" and "West"
    When the user dismisses the proposal for column "region"
    And the dataset is profiled again
    Then no proposal for column "region" is offered
    And after the app restarts no proposal for column "region" is offered

  # AC-9
  Scenario: The profile reflects an approved standardization
    Given an ingested sales file where case variants of "East" carry amounts 10, 20 and 30 and "West" carries 40
    When the user approves the proposed rule for column "region"
    Then the "region" column's profile counts 2 distinct values
    And the profile's example values include "East" and no other case variant of it

  # AC-10
  Scenario: Approved rules survive a restart
    Given an ingested sales file where case variants of "East" carry amounts 10, 20 and 30 and "West" carries 40
    And the proposed rule for column "region" is approved
    When the app restarts
    Then the total amount by region still shows "East" at 60

  # AC-11 (folded error case)
  Scenario: Acting on a proposal that no longer exists fails cleanly
    Given an ingested file whose "region" column holds "East", "east", "EAST", "West" and "West"
    When the user approves a proposal that does not exist
    Then the action is rejected as not found
    And the distinct values of "region" are unchanged

## Workbench flow (browser)

  # AC-11
  Scenario: The workbench carries the approval flow
    Given the analyst app is open in a browser
    When the user opens the sample sales table in the workbench
    Then the column "region" visibly indicates a pending proposal
    When the user opens the column "region"
    Then the proposal is visible with its variants
    When the user approves the proposal in the workbench
    Then the workbench shows the proposal as applied without a page reload

  # AC-11
  Scenario: Dismissing in the workbench removes the proposal
    Given the analyst app is open in a browser
    When the user opens the column "region" of the sample sales table
    And the user dismisses its normalization proposal
    Then no normalization proposal remains on the column
