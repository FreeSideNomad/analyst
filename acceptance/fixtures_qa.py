"""Shared fixture data for the Q&A planner (feature 003).

Kept in one place so the live cassette-recorders, the unit replay tests, and
the acceptance e2e board build byte-identical planner inputs — the
record/replay key derives from the profiled workspace metadata, so the CSV
and the question strings must match exactly.
"""

from pathlib import Path

CASSETTE_DIR = Path(__file__).parent.parent / "tests" / "cassettes"
PLANNER_CASSETTE = CASSETTE_DIR / "planner.json"

# A small orders dataset with TWO region-ish columns, so "by region" is
# genuinely ambiguous while a workspace-wide total is not.
QA_ORDERS_CSV = (
    "order_id,customer,billing_region,ship_region,amount,order_date\n"
    "1,alice,East,West,120.00,2024-01-05\n"
    "2,bob,West,East,80.50,2024-01-09\n"
    "3,carol,East,East,200.00,2024-02-11\n"
    "4,dan,South,South,50.25,2024-02-14\n"
    "5,erin,North,North,175.75,2024-03-02\n"
    "6,frank,West,West,90.00,2024-03-18\n"
)
QA_ORDERS_TOTAL = "716.50"

QUESTION_DIRECT = "What is the total order amount across all orders?"
QUESTION_AMBIGUOUS = "What is the total order amount by region?"
QUESTION_OUT_OF_SCOPE = "What will the weather be in Toronto tomorrow?"

# AC-5 — a question paired (in tests only) with a SYNTHETIC planner response
# whose SQL references a column that does not exist. Test-authored by
# construction: it exercises the validation gate, it is not a model recording.
QUESTION_INVALID = "What is the total profit by region?"
INVALID_PLAN_RESPONSE = (
    '{"action": "answer", "confidence": 0.9,'
    ' "sql": "SELECT billing_region, SUM(profit) AS total_profit'
    ' FROM qa_orders GROUP BY billing_region",'
    ' "title": "Total profit by billing region",'
    ' "assumptions": ["Profit is a column on qa_orders."],'
    ' "lineage": ["qa_orders"], "clarification": null, "reason": null}'
)
