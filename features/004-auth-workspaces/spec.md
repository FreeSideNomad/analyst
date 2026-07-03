# Spec — Feature 004: Auth & workspaces

> Checkpoint 3. Standard Gherkin over the 13 approved ACs in `acs.md`.
> AC-1..8 bind over HTTP; AC-9..13 bind to a real browser (Playwright) — both
> against the API in fixtures mode with dev sign-in enabled, so every run is
> deterministic and needs no real OAuth credentials. Each scenario is tagged
> with its AC.

Feature: Auth & workspaces
  Users sign in (Google/Microsoft OAuth, or the dev sign-in for local runs);
  the first user becomes admin, creates workspaces and adds members; datasets
  and catalogs are isolated per workspace. Without any sign-in method
  configured the service behaves exactly as before.

## API contract (HTTP)

  # AC-1
  Scenario: The service reports which sign-in methods are available
    Given the analyst service is running with dev sign-in enabled
    When a client asks which sign-in methods are available
    Then dev sign-in is offered
    And Google and Microsoft sign-in are reported as not configured

  # AC-2
  Scenario: Signed-out clients cannot reach workspace data
    Given the analyst service is running with dev sign-in enabled
    When a signed-out client lists the datasets
    Then the request is rejected as unauthenticated
    When a signed-out client checks the service health
    Then the service answers that it is healthy

  # AC-3
  Scenario: The first user becomes admin with a default workspace
    Given the analyst service is running with dev sign-in enabled
    When "Ana" signs in for the first time
    Then "Ana" is an admin with a default workspace
    When "Ben" signs in for the first time
    Then "Ben" is not an admin and belongs to no workspace

  # AC-4
  Scenario: The admin creates a workspace and adds a member
    Given "Ana" has signed in as the first user
    When "Ana" creates the workspace "Finance"
    And "Ana" adds "Ben" as a member of "Finance"
    Then "Ben" sees the workspace "Finance" after signing in
    And "Ben" cannot create workspaces

  # AC-5
  Scenario: Datasets are isolated per workspace
    Given "Ana" has signed in as the first user
    And "Ana" has created and switched to the workspace "Finance"
    When "Ana" deletes the dataset "sales"
    And "Ana" switches back to her default workspace
    Then the dataset "sales" is still present
    And the workspace "Finance" no longer contains "sales"

  # AC-6
  Scenario: Signing out ends the session
    Given "Ana" has signed in as the first user
    When "Ana" signs out
    Then her previous session can no longer list the datasets

  # AC-7
  Scenario: An unconfigured sign-in provider is refused clearly
    Given the analyst service is running with dev sign-in enabled
    When a client starts a Google sign-in
    Then the sign-in is refused because Google is not configured

  # AC-8
  Scenario: Without any sign-in method the service behaves as before
    Given an analyst service with no sign-in method configured
    When a client lists the datasets without signing in
    Then the datasets are served normally

## Frontend flows (browser)

  # AC-9
  Scenario: A visitor signs in with the dev sign-in
    Given the analyst app is open in a browser
    Then the sign-in page is shown
    When the visitor signs in as "Ana"
    Then the workspace app appears with "Ana" shown in the header

  # AC-10
  Scenario: The sign-in page says OAuth is not configured
    Given the analyst app is open in a browser
    Then the sign-in page says Google sign-in is not configured
    And the sign-in page says Microsoft sign-in is not configured

  # AC-11
  Scenario: The admin creates a workspace and data stays isolated
    Given "Ana" is signed in to the app
    When she deletes the dataset "sales"
    And she creates and switches to the workspace "Finance"
    Then the semantic catalog lists "sales.csv"
    When she switches to her default workspace
    Then "sales.csv" is absent from the semantic catalog

  # AC-12
  Scenario: Signing out returns to the sign-in page
    Given "Ana" is signed in to the app
    When she signs out
    Then the sign-in page is shown

  # AC-13
  Scenario: A member without a workspace sees a notice
    Given "Ana" is signed in to the app
    When she signs out
    And the visitor signs in as "Ben"
    Then a notice explains that no workspace has been assigned yet
