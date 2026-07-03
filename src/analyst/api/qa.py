"""Provisional Q&A service (feature 002).

The domain has no query/answer model yet — only the `Clarification` primitive.
This module returns the API-schema Q&A shapes so the frontend has a stable
contract to build against. When feature 002 lands, these become adapters over
real domain objects; the wire shape should not need to change.

Routing is keyword-based over the canned answers (a stand-in for the agent's
semantic-catalog planner).
"""

from __future__ import annotations

from analyst.api.schemas import (
    AnswerResult,
    ChartPoint,
    ClarificationResult,
    QueryResult,
    StatBlock,
    TrustTrailSchema,
)

_REGION_CLARIFY = ClarificationResult(
    query_id="qry-clarify-001",
    question="Two region columns are available. Which one should I use?",
    column="region",
    options=[
        "billing_region — sales billing region (237 nulls, 4 distinct)",
        "region — customer region (no nulls, 4 distinct)",
    ],
)


def _revenue_answer(choice_label: str) -> AnswerResult:
    return AnswerResult(
        query_id="qry-answer-001",
        chart_type="bar",
        chart_title=f"Revenue by {choice_label}",
        highlight="East",
        nice_max=5_000_000,
        tick_step=1_000_000,
        summary=(
            f"Total FY2024 revenue by {choice_label.lower()}. The East region "
            "generated the most at $4.2M, followed by North at $3.8M. Four "
            "regions cover 99.8% of orders."
        ),
        chart_data=[
            ChartPoint(label="East", value=4_218_340),
            ChartPoint(label="North", value=3_812_150),
            ChartPoint(label="South", value=2_945_600),
            ChartPoint(label="West", value=1_673_900),
        ],
        trust_trail=TrustTrailSchema(
            assumptions=[
                "Revenue is calculated as quantity × unit_price.",
                "Rows with a NULL region (237 of 143,209) are excluded.",
                "Scope limited to fiscal year 2024 (order_date).",
            ],
            lineage=[
                "sales (ds-sales-001)",
                "Columns: billing_region, quantity, unit_price",
                "Filter: order_date BETWEEN '2024-01-01' AND '2024-12-31'",
            ],
            sql=(
                "SELECT\n  billing_region,\n  SUM(quantity * unit_price) AS total_revenue\n"
                "FROM sales\nWHERE order_date BETWEEN '2024-01-01' AND '2024-12-31'\n"
                "  AND billing_region IS NOT NULL\nGROUP BY billing_region\n"
                "ORDER BY total_revenue DESC;"
            ),
        ),
    )


_TOP_CUSTOMERS = AnswerResult(
    query_id="qry-multi-001",
    chart_type="bar",
    chart_title="Top 5 customers by revenue",
    highlight="Acme Corp",
    nice_max=500_000,
    tick_step=100_000,
    summary=(
        "Top 5 customers by total revenue in 2024. Acme Corp leads with $482K, "
        "followed by Globex Inc at $391K. Customer names resolved via a join on "
        "customer_id."
    ),
    chart_data=[
        ChartPoint(label="Acme Corp", value=482_100),
        ChartPoint(label="Globex Inc", value=391_400),
        ChartPoint(label="Initech LLC", value=287_600),
        ChartPoint(label="Umbrella Co", value=245_900),
        ChartPoint(label="Stark Industries", value=198_300),
    ],
    trust_trail=TrustTrailSchema(
        assumptions=[
            "Revenue = quantity × unit_price from the sales table.",
            "Customer names resolved via an inner join on customer_id.",
            "Only fiscal-year-2024 orders are included.",
        ],
        lineage=[
            "sales (ds-sales-001), customers (ds-customers-002)",
            "Join: sales.customer_id = customers.customer_id",
            "Columns: customer_name, quantity, unit_price, order_date",
        ],
        sql=(
            "SELECT\n  c.customer_name,\n  SUM(s.quantity * s.unit_price) AS total_revenue\n"
            "FROM sales s\nINNER JOIN customers c\n  ON s.customer_id = c.customer_id\n"
            "WHERE s.order_date BETWEEN '2024-01-01' AND '2024-12-31'\n"
            "GROUP BY c.customer_name\nORDER BY total_revenue DESC\nLIMIT 5;"
        ),
    ),
)

_AOV = AnswerResult(
    query_id="qry-aov-001",
    chart_type="stat",
    chart_title="Average order value",
    summary=(
        "The average order value in 2024 is $367.42 — total revenue divided by "
        "the count of distinct orders."
    ),
    stat=StatBlock(
        value="$367.42",
        label="Average order value · FY2024",
        sub="across 143,209 distinct orders",
    ),
    trust_trail=TrustTrailSchema(
        assumptions=[
            "Order value = SUM(quantity × unit_price) per order_id.",
            "All 143,209 orders in FY2024 are included; none excluded.",
        ],
        lineage=["sales (ds-sales-001)", "Columns: order_id, quantity, unit_price"],
        sql=(
            "WITH per_order AS (\n  SELECT order_id, SUM(quantity * unit_price) AS order_total\n"
            "  FROM sales\n  WHERE order_date BETWEEN '2024-01-01' AND '2024-12-31'\n"
            "  GROUP BY order_id\n)\nSELECT ROUND(AVG(order_total), 2) AS avg_order_value\n"
            "FROM per_order;"
        ),
    ),
)


def _abstain() -> AnswerResult:
    return AnswerResult(
        query_id="qry-abstain",
        abstain=True,
        chart_type="none",
        summary=(
            "I can't answer that from the current catalog. This workspace covers "
            "the sales, customers and products datasets — try asking about "
            "revenue, regions, channels, customers or products."
        ),
    )


def submit_query(question: str) -> QueryResult:
    q = question.lower()
    if "region" in q or ("revenue" in q and "by" in q):
        return _REGION_CLARIFY
    if "customer" in q and ("top" in q or "5" in q or "five" in q):
        return _TOP_CUSTOMERS
    if "average" in q or "aov" in q or "order value" in q:
        return _AOV
    if "revenue" in q:
        return _REGION_CLARIFY
    return _abstain()


def respond(query_id: str, selected_options: list[str]) -> AnswerResult:
    choice = selected_options[0] if selected_options else ""
    label = "Billing region" if "billing" in choice.lower() else "Customer region"
    return _revenue_answer(label)
