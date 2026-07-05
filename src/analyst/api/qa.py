"""Q&A services (feature 003) — the confidence-gated brain behind /api/query.

Two implementations of one seam, on the UNCHANGED wire contract:

- ``PlannerQAService`` (real mode, default) — the agentic planner: workspace
  catalog metadata -> QueryPlanner (through the LLMGateway) -> closed-world
  SQL validation -> local DuckDB execution -> a deterministically shaped
  answer carrying the trust trail (assumptions, lineage, executed SQL).
  SQL that fails validation is NEVER executed — the service abstains.
- ``CannedQAService`` (fixtures mode) — the feature-002 deterministic path,
  kept verbatim so UI e2e stays LLM-free.
"""

from __future__ import annotations

import math
import os
import uuid
from typing import Protocol

from analyst.agentic.gateway import LLMGateway, ReplayBackend
from analyst.agentic.planner import QueryPlanner
from analyst.api.repository import DatasetRecord, DatasetRepository, StoreRepository
from analyst.api.schemas import (
    AnswerResult,
    ChartPoint,
    ClarificationResult,
    QueryResult,
    StatBlock,
    TrustTrailSchema,
)
from analyst.domain.catalog import Clarification
from analyst.domain.query import (
    PlanAction,
    QueryPlan,
    QueryTable,
    ResultTable,
    query_table_from_summary,
)
from analyst.domain.query_validation import validate_sql
from analyst.engine.query import run_select


class QAService(Protocol):
    """The seam the Q&A routes call. ``respond`` returns None for unknown ids."""

    mode: str

    def submit(self, question: str, repo: DatasetRepository) -> QueryResult: ...
    def respond(
        self, query_id: str, selected_options: list[str], repo: DatasetRepository
    ) -> AnswerResult | None: ...


# --------------------------------------------------------------------------- #
# Real mode — the agentic planner over the local DuckDB store.
# --------------------------------------------------------------------------- #
def _query_id() -> str:
    return f"qry-{uuid.uuid4().hex[:8]}"


def _abstain_answer(summary: str) -> AnswerResult:
    return AnswerResult(
        query_id=_query_id(), abstain=True, chart_type="none", summary=summary
    )


def _format_value(value: object) -> str:
    if isinstance(value, bool) or value is None:
        return str(value)
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{value:,.2f}"
    return str(value)


def _nice_ceiling(value: float) -> float:
    """The smallest 'nice' number (1/2/2.5/5 x 10^k) at or above ``value``."""
    if value <= 0:
        return 1.0
    exponent = math.floor(math.log10(value))
    for mantissa in (1.0, 2.0, 2.5, 5.0, 10.0):
        candidate = mantissa * 10.0**exponent
        if value <= candidate:
            return candidate
    return 10.0 ** (exponent + 1)


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _shape_answer(plan: QueryPlan, result: ResultTable) -> AnswerResult:
    """Deterministically shape the locally computed result (no second model
    call — no result rows need to cross to the model at all)."""
    assert plan.sql is not None
    trail = TrustTrailSchema(
        assumptions=list(plan.assumptions),
        lineage=list(plan.lineage),
        sql=plan.sql,
    )
    title = plan.title or "Result"

    if not result.rows:
        return AnswerResult(
            query_id=_query_id(),
            summary=f"{title}: the query returned no rows.",
            chart_type="none",
            trust_trail=trail,
        )

    if len(result.rows) == 1 and len(result.columns) == 1:
        value = _format_value(result.rows[0][0])
        sub = plan.lineage[0] if plan.lineage else "computed locally in DuckDB"
        return AnswerResult(
            query_id=_query_id(),
            summary=f"{title}: {value}.",
            chart_type="stat",
            chart_title=title,
            stat=StatBlock(value=value, label=title, sub=sub),
            trust_trail=trail,
        )

    bar_worthy = (
        len(result.columns) == 2
        and 2 <= len(result.rows) <= 12
        and all(_is_number(row[1]) for row in result.rows)
    )
    if bar_worthy:
        points = [
            ChartPoint(label=str(row[0]), value=float(row[1]))  # type: ignore[arg-type]
            for row in result.rows
        ]
        top = max(points, key=lambda p: p.value)
        nice_max = _nice_ceiling(top.value)
        return AnswerResult(
            query_id=_query_id(),
            summary=f"{title}. {top.label} leads at {_format_value(top.value)}.",
            chart_type="bar",
            chart_title=title,
            highlight=top.label,
            nice_max=nice_max,
            tick_step=nice_max / 4,
            chart_data=points,
            trust_trail=trail,
        )

    shown = min(len(result.rows), 3)
    preview = "; ".join(
        ", ".join(_format_value(v) for v in row) for row in result.rows[:shown]
    )
    more = " (truncated)" if result.truncated else ""
    return AnswerResult(
        query_id=_query_id(),
        summary=f"{title}: {len(result.rows)} row(s){more}. First rows: {preview}.",
        chart_type="none",
        trust_trail=trail,
    )


class PlannerQAService:
    """Real mode: plan -> validate -> execute locally -> shaped answer."""

    mode = "real"

    def __init__(self, planner: QueryPlanner):
        self.planner = planner
        self._pending: dict[str, tuple[str, Clarification]] = {}

    def _tables(self, repo: DatasetRepository) -> tuple[QueryTable, ...]:
        # Local file datasets, plus connected-DB tables that are ATTACHed and
        # therefore runnable (feature 007). Bridge-only federated tables stay
        # excluded so the planner never writes un-runnable SQL.
        def queryable(r: DatasetRecord) -> bool:
            return not getattr(r, "federated", False) or getattr(
                r, "db_queryable", False
            )

        records = sorted(
            (r for r in repo.list_datasets() if queryable(r)),
            key=lambda r: r.name,
        )
        return tuple(query_table_from_summary(r.summary) for r in records)

    def _relationships(self, repo: DatasetRepository) -> tuple:
        """Discovered relationships (feature 009) across the queryable tables, so
        the planner joins on the right keys with the right join type (007)."""
        out: list = []
        for r in repo.list_datasets():
            catalog = getattr(r.summary, "catalog", None)
            out.extend(getattr(catalog, "relationships", ()) or ())
        return tuple(out)

    def submit(self, question: str, repo: DatasetRepository) -> QueryResult:
        tables = self._tables(repo)
        if not tables:
            return _abstain_answer(
                "No datasets are loaded yet — ingest a file first, then ask again."
            )
        plan = self.planner.plan(question, tables, self._relationships(repo))
        return self._realize(plan, question, tables, repo)

    def respond(
        self, query_id: str, selected_options: list[str], repo: DatasetRepository
    ) -> AnswerResult | None:
        pending = self._pending.pop(query_id, None)
        if pending is None:
            return None
        question, clarification = pending
        tables = self._tables(repo)
        choice = selected_options[0] if selected_options else ""
        plan = self.planner.replan(
            question, tables, clarification, choice, self._relationships(repo)
        )
        realized = self._realize(plan, question, tables, repo)
        if isinstance(realized, ClarificationResult):
            # The wire contract: respond always yields an answer.
            return _abstain_answer(
                "The question is still ambiguous after that choice — "
                "try rephrasing it with the column you mean."
            )
        return realized

    def _realize(
        self,
        plan: QueryPlan,
        question: str,
        tables: tuple[QueryTable, ...],
        repo: DatasetRepository,
    ) -> QueryResult:
        if plan.action is PlanAction.CLARIFY:
            assert plan.clarification is not None
            query_id = _query_id()
            self._pending[query_id] = (question, plan.clarification)
            return ClarificationResult(
                query_id=query_id,
                question=plan.clarification.question,
                options=list(plan.clarification.options),
                column=plan.clarification.column,
            )

        if plan.action is PlanAction.ABSTAIN:
            coverage = ", ".join(t.name for t in tables)
            reason = plan.reason or "The question is outside the loaded datasets."
            return _abstain_answer(
                f"I can't answer that from the current catalog. {reason} "
                f"This workspace covers: {coverage}."
            )

        assert plan.sql is not None  # guaranteed by the planner for ANSWER
        schema = {t.name: tuple(c.name for c in t.columns) for t in tables}
        problems = validate_sql(plan.sql, schema)
        if problems:
            return _abstain_answer(
                "The generated SQL failed validation and was not executed: "
                + " ".join(problems)
            )

        if not isinstance(repo, StoreRepository):
            return _abstain_answer(
                "Real Q&A needs the real dataset store; fixtures mode serves "
                "the canned path instead."
            )
        try:
            result = run_select(repo.store, plan.sql)
        except Exception as exc:
            return _abstain_answer(f"The query could not be executed: {exc}")
        return _shape_answer(plan, result)


def build_qa_service(repo: DatasetRepository) -> QAService:
    """Fixtures repo -> canned; real store -> the agentic planner.

    ``ANALYST_QA_CASSETTE`` points the real planner at recorded responses
    (deterministic replay — the e2e/demo seam); otherwise the live Claude
    Agent SDK backend serves.
    """
    if not isinstance(repo, StoreRepository):
        return CannedQAService()
    cassette = os.environ.get("ANALYST_QA_CASSETTE")
    if cassette:
        return PlannerQAService(QueryPlanner(LLMGateway(ReplayBackend(cassette))))
    from analyst.agentic.claude_backend import ClaudeAgentBackend

    return PlannerQAService(QueryPlanner(LLMGateway(ClaudeAgentBackend())))


# --------------------------------------------------------------------------- #
# Fixtures mode — the feature-002 canned path, kept verbatim (deterministic,
# LLM-free; the UI e2e suite drives it).
# --------------------------------------------------------------------------- #
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


def _canned_abstain() -> AnswerResult:
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


class CannedQAService:
    """Keyword-routed canned answers — feature 002 behavior.

    One routing fix over 002: the top-customers check runs before the
    region-clarify check, so the suggested "top 5 customers by revenue"
    question reaches its intended canned answer.
    """

    mode = "canned"

    def submit(self, question: str, repo: DatasetRepository) -> QueryResult:
        q = question.lower()
        if "customer" in q and ("top" in q or "5" in q or "five" in q):
            return _TOP_CUSTOMERS
        if "region" in q or ("revenue" in q and "by" in q):
            return _REGION_CLARIFY
        if "average" in q or "aov" in q or "order value" in q:
            return _AOV
        if "revenue" in q:
            return _REGION_CLARIFY
        return _canned_abstain()

    def respond(
        self, query_id: str, selected_options: list[str], repo: DatasetRepository
    ) -> AnswerResult | None:
        choice = selected_options[0] if selected_options else ""
        label = "Billing region" if "billing" in choice.lower() else "Customer region"
        return _revenue_answer(label)
