# Spec — Feature 003: Natural-language Q&A over a dataset

> Checkpoint 3. Standard Gherkin over the 10 approved ACs in `acs.md`.
> AC-1..AC-7 bind over HTTP; AC-8..AC-10 bind to a real browser (Playwright)
> against the fixtures API. Real-planner scenarios (AC-1..AC-5) run against a
> service whose model responses are recorded-real and replayed — every run is
> deterministic and LLM-free. Each scenario is tagged with its AC.

Feature: Natural-language Q&A over a dataset
  A user asks a plain-English question about the loaded datasets and gets a
  confidence-gated response — a direct answer when confident, a structured
  AskQuestion clarification when ambiguous, an abstention when out-of-scope —
  always carrying the expandable trust trail (assumptions, lineage, SQL).

## API contract (HTTP)

  # AC-1
  Scenario: A confident question is answered directly with a trust trail
    Given the analyst service is running with the real query planner and the dataset "qa_orders"
    When the user asks the planner "What is the total order amount across all orders?"
    Then a direct answer is returned carrying a summary and a trust trail
    And the answer reflects the locally computed total of "716.50"
    And the trust trail discloses the SQL that was executed

  # AC-2
  Scenario: An ambiguous question yields a structured clarification
    Given the analyst service is running with the real query planner and the dataset "qa_orders"
    When the user asks the planner "What is the total order amount by region?"
    Then a clarification is returned offering the candidate region columns

  # AC-3
  Scenario: Answering the clarification completes the query
    Given the analyst service is running with the real query planner and the dataset "qa_orders"
    When the user asks the planner "What is the total order amount by region?"
    And the user answers the clarification with its first option
    Then a direct answer is returned carrying a summary and a trust trail
    And the trust trail SQL uses the chosen region column

  # AC-4
  Scenario: An out-of-scope question abstains rather than fabricates
    Given the analyst service is running with the real query planner and the dataset "qa_orders"
    When the user asks the planner "What will the weather be in Toronto tomorrow?"
    Then the service abstains from answering
    And the abstention fabricates no chart and no SQL

  # AC-5
  Scenario: A plan referencing unknown columns is never executed
    Given the analyst service is running with the real query planner and the dataset "qa_orders"
    When the user asks the planner a question whose generated SQL references a column that does not exist
    Then the service abstains from answering
    And the abstention fabricates no chart and no SQL

  # AC-6
  Scenario: Health reports the real Q&A engine when the real planner serves
    Given the analyst service is running with the real query planner and the dataset "qa_orders"
    When a client checks that service's health
    Then the health reports the Q&A engine "real"

  # AC-6
  Scenario: Health reports the canned Q&A engine in fixtures mode
    Given the analyst service is running with mocked data
    When a client checks the fixtures service's health
    Then the health reports the Q&A engine "canned"

  # AC-7
  Scenario: Fixtures mode keeps the deterministic clarify-then-answer contract
    Given the analyst service is running with mocked data
    When a client submits the canned question "What is the revenue by region?"
    Then a clarification is returned offering the candidate region columns
    When the user answers the clarification with its first option
    Then a direct answer is returned carrying a summary and a trust trail

  # AC-7
  Scenario: Fixtures mode abstains deterministically when out of scope
    Given the analyst service is running with mocked data
    When a client submits the canned question "What will the weather be tomorrow?"
    Then the service abstains from answering

## Frontend flows (browser)

  # AC-8
  Scenario: An out-of-scope question visibly abstains in the chat
    Given the analyst app is open in a browser
    When the user asks in the chat "What will the weather be tomorrow?"
    Then the chat shows an abstention naming what the workspace covers
    And the abstention shows no chart and no trust trail

  # AC-9
  Scenario: A confident question renders a stat answer with its trust trail
    Given the analyst app is open in a browser
    When the user asks in the chat "What is the average order value?"
    Then a stat answer appears showing the value "$367.42"
    And the trust trail is expandable down to the SQL

  # AC-9 — behavior pin (fix investigation 2026-07-08: reported self-collapse
  # was not reproducible; the trail opens by default on the latest answer)
  Scenario: The latest answer's trust trail arrives expanded and stays expanded
    Given the analyst app is open in a browser
    When the user asks in the chat "What is the average order value?"
    Then the trust trail is already expanded showing its assumptions
    And the trust trail stays expanded

  # AC-10
  Scenario: An aggregate answer renders as a chart with its leader highlighted
    Given the analyst app is open in a browser
    When the user asks in the chat "Who are the top 5 customers by revenue?"
    Then a bar chart answer appears led by "Acme Corp"
    And the trust trail SQL reveals the join behind the chart
