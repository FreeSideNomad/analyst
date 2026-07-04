"""Feature 003 — the real Q&A service behind the unchanged wire contract.

PlannerQAService orchestrates: catalog metadata -> plan (replayed real model
responses) -> closed-world SQL validation -> local DuckDB execution -> shaped
answer with a trust trail. Fixtures mode keeps the canned deterministic path.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from acceptance.fixtures_qa import (
    INVALID_PLAN_RESPONSE,
    PLANNER_CASSETTE,
    QA_ORDERS_CSV,
    QUESTION_AMBIGUOUS,
    QUESTION_DIRECT,
    QUESTION_OUT_OF_SCOPE,
)
from analyst.agentic.gateway import LLMGateway, ReplayBackend
from analyst.agentic.planner import QueryPlanner
from analyst.api.app import create_app
from analyst.api.qa import CannedQAService, PlannerQAService, build_qa_service
from analyst.api.repository import FixtureRepository, StoreRepository

needs_cassette = pytest.mark.skipif(
    not PLANNER_CASSETTE.exists(), reason="planner cassette not recorded yet"
)


class ScriptBackend:
    """Returns scripted responses in order — for governance-path tests."""

    def __init__(self, *responses: str):
        self.responses = list(responses)

    def complete(self, request):  # noqa: ANN001, ANN201
        return self.responses.pop(0)


class ExplodingBackend:
    def complete(self, request):  # noqa: ANN001, ANN201
        raise AssertionError("the model must not be called")


def _real_client(tmp_path, backend) -> TestClient:
    repo = StoreRepository(str(tmp_path / "data"))
    app = create_app(repo)
    app.state.qa_holder = {
        "service": PlannerQAService(QueryPlanner(LLMGateway(backend)))
    }
    return TestClient(app)


def _ingest_orders(client: TestClient) -> None:
    response = client.post(
        "/api/datasets/ingest",
        files={"file": ("qa_orders.csv", QA_ORDERS_CSV.encode())},
    )
    assert response.status_code == 200


# --------------------------------------------------------------------------- #
# AC-1 — direct answer, locally executed, with a trust trail.
# --------------------------------------------------------------------------- #
@needs_cassette
def test_direct_question_answers_with_locally_computed_value(tmp_path):
    client = _real_client(tmp_path, ReplayBackend(PLANNER_CASSETTE))
    _ingest_orders(client)
    answer = client.post("/api/query", json={"question": QUESTION_DIRECT}).json()
    assert answer["type"] == "answer" and not answer.get("abstain")
    assert "716.50" in answer["summary"]
    assert answer["chartType"] == "stat" and answer["stat"]["value"] == "716.50"
    trail = answer["trustTrail"]
    assert trail["assumptions"] and trail["lineage"]
    assert "select" in trail["sql"].lower()


# --------------------------------------------------------------------------- #
# AC-2 / AC-3 — clarify, then answer with the chosen column.
# --------------------------------------------------------------------------- #
@needs_cassette
def test_ambiguous_question_clarifies_then_answers(tmp_path):
    client = _real_client(tmp_path, ReplayBackend(PLANNER_CASSETTE))
    _ingest_orders(client)
    clarification = client.post(
        "/api/query", json={"question": QUESTION_AMBIGUOUS}
    ).json()
    assert clarification["type"] == "clarification"
    assert len(clarification["options"]) >= 2
    answer = client.post(
        f"/api/query/{clarification['queryId']}/respond",
        json={"selectedOptions": [clarification["options"][0]]},
    ).json()
    assert answer["type"] == "answer" and not answer.get("abstain")
    assert answer["chartType"] == "bar" and answer["chartData"]
    assert "billing_region" in answer["trustTrail"]["sql"]
    # East leads: 120.00 + 200.00 = 320.00
    assert answer["highlight"] == "East"


# --------------------------------------------------------------------------- #
# AC-4 — out-of-scope abstains: no chart, no SQL, no fabrication.
# --------------------------------------------------------------------------- #
@needs_cassette
def test_out_of_scope_question_abstains(tmp_path):
    client = _real_client(tmp_path, ReplayBackend(PLANNER_CASSETTE))
    _ingest_orders(client)
    answer = client.post("/api/query", json={"question": QUESTION_OUT_OF_SCOPE}).json()
    assert answer["type"] == "answer" and answer["abstain"] is True
    assert answer["chartType"] == "none"
    assert answer.get("chartData") is None and answer.get("trustTrail") is None


# --------------------------------------------------------------------------- #
# AC-5 — invalid SQL is never executed.
# --------------------------------------------------------------------------- #
def test_sql_referencing_unknown_columns_is_never_executed(tmp_path, monkeypatch):
    import analyst.api.qa as qa_mod

    def _must_not_run(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        raise AssertionError("unvalidated SQL must never execute")

    monkeypatch.setattr(qa_mod, "run_select", _must_not_run)
    client = _real_client(tmp_path, ScriptBackend(INVALID_PLAN_RESPONSE))
    _ingest_orders(client)
    answer = client.post("/api/query", json={"question": "anything"}).json()
    assert answer["abstain"] is True
    assert "validation" in answer["summary"].lower()
    assert answer.get("trustTrail") is None


def test_non_select_sql_is_never_executed(tmp_path, monkeypatch):
    import analyst.api.qa as qa_mod

    monkeypatch.setattr(
        qa_mod,
        "run_select",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not execute")),
    )
    response = json.dumps(
        {
            "action": "answer",
            "confidence": 0.95,
            "sql": "DROP TABLE qa_orders",
            "assumptions": [],
            "lineage": ["qa_orders"],
        }
    )
    client = _real_client(tmp_path, ScriptBackend(response))
    _ingest_orders(client)
    answer = client.post("/api/query", json={"question": "anything"}).json()
    assert answer["abstain"] is True


# --------------------------------------------------------------------------- #
# Answer shaping — label/value results become a bar chart, locally computed.
# --------------------------------------------------------------------------- #
def test_group_by_result_is_shaped_as_a_bar_chart(tmp_path):
    response = json.dumps(
        {
            "action": "answer",
            "confidence": 0.9,
            "sql": (
                "SELECT billing_region, SUM(amount) AS total_amount "
                "FROM qa_orders GROUP BY billing_region "
                "ORDER BY total_amount DESC"
            ),
            "title": "Total order amount by billing region",
            "assumptions": ["Amounts are summed per billing region."],
            "lineage": ["qa_orders: billing_region, amount"],
        }
    )
    client = _real_client(tmp_path, ScriptBackend(response))
    _ingest_orders(client)
    answer = client.post("/api/query", json={"question": "by region?"}).json()
    assert answer["chartType"] == "bar"
    assert answer["highlight"] == "East"
    labels = {p["label"] for p in answer["chartData"]}
    assert labels == {"East", "West", "North", "South"}
    assert answer["niceMax"] >= 320.0
    assert answer["tickStep"] > 0


def test_empty_result_answers_plainly_with_the_trail(tmp_path):
    response = json.dumps(
        {
            "action": "answer",
            "confidence": 0.9,
            "sql": "SELECT customer FROM qa_orders WHERE amount > 10000",
            "title": "Orders over 10000",
            "assumptions": [],
            "lineage": ["qa_orders"],
        }
    )
    client = _real_client(tmp_path, ScriptBackend(response))
    _ingest_orders(client)
    answer = client.post("/api/query", json={"question": "big orders?"}).json()
    assert answer["chartType"] == "none" and not answer.get("abstain")
    assert "no rows" in answer["summary"].lower()
    assert answer["trustTrail"]["sql"]


# --------------------------------------------------------------------------- #
# Guard rails
# --------------------------------------------------------------------------- #
def test_empty_workspace_abstains_without_calling_the_model(tmp_path):
    client = _real_client(tmp_path, ExplodingBackend())
    answer = client.post("/api/query", json={"question": "anything"}).json()
    assert answer["abstain"] is True


def test_responding_to_an_unknown_query_id_is_not_found(tmp_path):
    client = _real_client(tmp_path, ExplodingBackend())
    response = client.post(
        "/api/query/qry-nope/respond", json={"selectedOptions": ["x"]}
    )
    assert response.status_code == 404


# --------------------------------------------------------------------------- #
# AC-6 / AC-7 — mode selection and the retained canned path.
# --------------------------------------------------------------------------- #
def test_health_reports_qa_engine_mode(monkeypatch, tmp_path):
    monkeypatch.setenv("ANALYST_FIXTURES", "1")
    body = TestClient(create_app(FixtureRepository())).get("/api/health").json()
    assert body["qa"] == "canned"
    monkeypatch.delenv("ANALYST_FIXTURES")
    monkeypatch.setenv("ANALYST_DATA_DIR", str(tmp_path / "d"))
    body = (
        TestClient(create_app(StoreRepository(str(tmp_path / "d"))))
        .get("/api/health")
        .json()
    )
    assert body["qa"] == "real"


def test_service_selection_follows_the_repository(tmp_path, monkeypatch):
    assert isinstance(build_qa_service(FixtureRepository()), CannedQAService)
    monkeypatch.setenv("ANALYST_QA_CASSETTE", str(PLANNER_CASSETTE))
    service = build_qa_service(StoreRepository(str(tmp_path / "data")))
    assert isinstance(service, PlannerQAService)


def test_canned_service_keeps_the_feature_002_contract():
    canned = CannedQAService()
    repo = FixtureRepository()
    clarification = canned.submit("What is the revenue by region?", repo)
    assert clarification.type == "clarification"
    answer = canned.respond("any-id", ["billing_region — sales billing"], repo)
    assert answer is not None and answer.type == "answer"
    assert answer.trust_trail is not None
    abstain = canned.submit("What will the weather be tomorrow?", repo)
    assert abstain.type == "answer" and abstain.abstain is True
