"""Feature 003 — the NL->SQL query planner (AC-1..AC-4) via the LLMGateway.

The `live` tests record REAL planning responses (Claude subscription) into
tests/cassettes/planner.json; the default tests replay them deterministically.
Record with:  uv run pytest -m live tests/unit/test_planner.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from acceptance.fixtures_qa import (
    PLANNER_CASSETTE,
    QA_ORDERS_CSV,
    QUESTION_AMBIGUOUS,
    QUESTION_DIRECT,
    QUESTION_OUT_OF_SCOPE,
)
from analyst.agentic.gateway import EgressLog, LLMGateway, ReplayBackend, StubBackend
from analyst.agentic.planner import QueryPlanner
from analyst.domain.query import PlanAction, QueryTable, query_table_from_summary
from analyst.domain.query_validation import validate_sql
from analyst.engine.store import DatasetStore
from analyst.service.ingestion import IngestionService


def _tables(tmp_path: Path) -> tuple[QueryTable, ...]:
    """Ingest the shared QA fixture CSV — identical for recording and replay."""
    csv = tmp_path / "qa_orders.csv"
    csv.write_text(QA_ORDERS_CSV, encoding="utf-8")
    result = IngestionService(DatasetStore(tmp_path / "store")).ingest(csv)
    return tuple(query_table_from_summary(s) for s in result.datasets)


def _schema(tables: tuple[QueryTable, ...]) -> dict[str, tuple[str, ...]]:
    return {t.name: tuple(c.name for c in t.columns) for t in tables}


def _replay_planner() -> QueryPlanner:
    return QueryPlanner(LLMGateway(ReplayBackend(PLANNER_CASSETTE)))


needs_cassette = pytest.mark.skipif(
    not PLANNER_CASSETTE.exists(), reason="planner cassette not recorded yet"
)


# --------------------------------------------------------------------------- #
# AC-1 — a confident question plans directly to validated SQL.
# --------------------------------------------------------------------------- #
@needs_cassette
def test_direct_question_plans_an_answer(tmp_path):
    tables = _tables(tmp_path)
    plan = _replay_planner().plan(QUESTION_DIRECT, tables)
    assert plan.action is PlanAction.ANSWER
    assert plan.sql and validate_sql(plan.sql, _schema(tables)) == []
    assert plan.assumptions and plan.lineage


# --------------------------------------------------------------------------- #
# AC-2 / AC-3 — ambiguity clarifies; the choice re-plans to an answer.
# --------------------------------------------------------------------------- #
@needs_cassette
def test_ambiguous_question_clarifies(tmp_path):
    plan = _replay_planner().plan(QUESTION_AMBIGUOUS, _tables(tmp_path))
    assert plan.action is PlanAction.CLARIFY
    assert plan.clarification is not None
    assert len(plan.clarification.options) >= 2


@needs_cassette
def test_clarification_choice_replans_to_an_answer(tmp_path):
    tables = _tables(tmp_path)
    planner = _replay_planner()
    clarify = planner.plan(QUESTION_AMBIGUOUS, tables)
    assert clarify.clarification is not None
    plan = planner.replan(
        QUESTION_AMBIGUOUS,
        tables,
        clarify.clarification,
        clarify.clarification.options[0],
    )
    assert plan.action is PlanAction.ANSWER
    assert plan.sql and validate_sql(plan.sql, _schema(tables)) == []
    assert "region" in plan.sql.lower()


# --------------------------------------------------------------------------- #
# AC-4 — out-of-scope questions abstain.
# --------------------------------------------------------------------------- #
@needs_cassette
def test_out_of_scope_question_abstains(tmp_path):
    plan = _replay_planner().plan(QUESTION_OUT_OF_SCOPE, _tables(tmp_path))
    assert plan.action is PlanAction.ABSTAIN
    assert plan.sql is None
    assert plan.reason


# --------------------------------------------------------------------------- #
# Robustness — no cassette needed.
# --------------------------------------------------------------------------- #
def test_unparseable_response_becomes_an_abstention(tmp_path):
    planner = QueryPlanner(LLMGateway(StubBackend("the model rambled, no JSON")))
    plan = planner.plan("anything", _tables(tmp_path))
    assert plan.action is PlanAction.ABSTAIN and plan.reason


def test_low_confidence_answers_are_demoted_to_abstention(tmp_path):
    response = json.dumps(
        {
            "action": "answer",
            "confidence": 0.2,
            "sql": "SELECT SUM(amount) FROM qa_orders",
            "assumptions": [],
            "lineage": ["qa_orders"],
        }
    )
    plan = QueryPlanner(LLMGateway(StubBackend(response))).plan(
        "anything", _tables(tmp_path)
    )
    assert plan.action is PlanAction.ABSTAIN
    assert plan.reason and "confidence" in plan.reason.lower()


def test_answer_without_sql_becomes_an_abstention(tmp_path):
    response = json.dumps({"action": "answer", "confidence": 0.9})
    plan = QueryPlanner(LLMGateway(StubBackend(response))).plan(
        "anything", _tables(tmp_path)
    )
    assert plan.action is PlanAction.ABSTAIN


# --------------------------------------------------------------------------- #
# Governance — planner egress goes through the gateway: capped + logged.
# --------------------------------------------------------------------------- #
def test_planner_egress_is_capped_and_logged(tmp_path):
    log = EgressLog()
    gateway = LLMGateway(StubBackend("{}"), egress_log=log, sample_cap=3)
    QueryPlanner(gateway).plan("anything", _tables(tmp_path))
    assert len(log.entries) == 1
    for col in log.entries[0]["columns"]:
        assert col["sample_count"] <= 3


def test_planner_prompt_is_deterministic(tmp_path):
    captured: list[str] = []

    class Capture:
        def complete(self, request):  # noqa: ANN001
            captured.append(request.prompt)
            return "{}"

    tables = _tables(tmp_path)
    QueryPlanner(LLMGateway(Capture())).plan("a question", tables)
    QueryPlanner(LLMGateway(Capture())).plan("a question", tuple(reversed(tables)))
    assert captured[0] == captured[1]


# --------------------------------------------------------------------------- #
# Live recorders — opt-in; hit the real subscription, write the cassette.
# --------------------------------------------------------------------------- #
@pytest.mark.live
def test_record_planner_cassette(tmp_path):
    from analyst.agentic.claude_backend import ClaudeAgentBackend
    from analyst.agentic.gateway import RecordingBackend

    tables = _tables(tmp_path)
    planner = QueryPlanner(
        LLMGateway(RecordingBackend(ClaudeAgentBackend(), PLANNER_CASSETTE))
    )

    direct = planner.plan(QUESTION_DIRECT, tables)
    print("DIRECT:", direct.action, direct.sql)
    assert direct.action is PlanAction.ANSWER, direct

    clarify = planner.plan(QUESTION_AMBIGUOUS, tables)
    print("AMBIGUOUS:", clarify.action, clarify.clarification)
    assert clarify.action is PlanAction.CLARIFY, clarify
    assert clarify.clarification is not None

    respond = planner.replan(
        QUESTION_AMBIGUOUS,
        tables,
        clarify.clarification,
        clarify.clarification.options[0],
    )
    print("RESPOND:", respond.action, respond.sql)
    assert respond.action is PlanAction.ANSWER, respond

    abstain = planner.plan(QUESTION_OUT_OF_SCOPE, tables)
    print("ABSTAIN:", abstain.action, abstain.reason)
    assert abstain.action is PlanAction.ABSTAIN, abstain
