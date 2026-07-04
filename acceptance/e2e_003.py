"""Step handlers for feature 003 — NL Q&A, bound to HTTP + a real browser.

Two stacks serve this board:

- The shared fixtures stack (``acceptance/e2e_base.py``): fixtures API + the
  production frontend build + Chromium — the canned deterministic Q&A path
  (AC-6..AC-10 fixtures/UI scenarios).
- A REAL-mode uvicorn (booted lazily, once per session): real DuckDB store +
  the agentic planner replaying RECORDED real model responses
  (``tests/cassettes/planner.json``) — AC-1..AC-6 exercise the genuine
  plan -> validate -> local-DuckDB path over HTTP with zero live calls.
  The AC-5 cassette entry (SQL referencing a nonexistent column) is
  synthesized here through the same planner code path — test-authored by
  construction, never presented as a model recording.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import httpx
import pytest

from acceptance.e2e_base import (
    _STACK,
    REPO_ROOT,
    ScenarioContext,
    _e2e_fresh,
    _e2e_stack,
    _free_port,
    _wait_http,
    expect_,
    make_registry,
)
from acceptance.fixtures_qa import (
    INVALID_PLAN_RESPONSE,
    PLANNER_CASSETTE,
    QA_ORDERS_CSV,
    QUESTION_INVALID,
)

step, run_step = make_registry()
_expect = expect_

__all__ = [
    "ScenarioContext",
    "run_step",
    "_e2e_stack",
    "_e2e_fresh",
    "_real_qa_stack",
]

_REAL: dict[str, Any] = {}


# --------------------------------------------------------------------------- #
# The real-mode stack (lazy; replayed real cassettes; no live model calls)
# --------------------------------------------------------------------------- #
def _merged_cassette(tmp_dir: Path) -> Path:
    """The committed recorded-real cassette + the synthetic AC-5 entry,
    keyed through the exact code path the server will use."""
    from analyst.agentic.gateway import LLMGateway
    from analyst.agentic.planner import QueryPlanner
    from analyst.domain.query import query_table_from_summary
    from analyst.engine.store import DatasetStore
    from analyst.service.ingestion import IngestionService

    records = json.loads(PLANNER_CASSETTE.read_text(encoding="utf-8"))

    csv = tmp_dir / "qa_orders.csv"
    csv.write_text(QA_ORDERS_CSV, encoding="utf-8")
    result = IngestionService(DatasetStore(tmp_dir / "probe-store")).ingest(csv)
    tables = tuple(query_table_from_summary(s) for s in result.datasets)

    class _Capture:
        request: Any = None

        def complete(self, request: Any) -> str:
            self.request = request
            return INVALID_PLAN_RESPONSE

    capture = _Capture()
    QueryPlanner(LLMGateway(capture)).plan(QUESTION_INVALID, tables)
    records[capture.request.key()] = INVALID_PLAN_RESPONSE

    path = tmp_dir / "planner_e2e.json"
    path.write_text(json.dumps(records), encoding="utf-8")
    return path


def _real_api() -> str:
    """Boot (once) a REAL-mode service: real store + replayed real planner."""
    if "api" in _REAL:
        return _REAL["api"]
    tmp = Path(tempfile.mkdtemp(prefix="analyst-e2e-003-"))
    cassette = _merged_cassette(tmp)
    port = _free_port()
    api = f"http://127.0.0.1:{port}"
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "analyst.api.app:app",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "ANALYST_FIXTURES": "0",
            "ANALYST_DATA_DIR": str(tmp / "data"),
            "ANALYST_QA_CASSETTE": str(cassette),
        },
    )
    _REAL.update(api=api, proc=proc)
    _wait_http(f"{api}/api/health")
    response = httpx.post(
        f"{api}/api/datasets/ingest",
        files={"file": ("qa_orders.csv", QA_ORDERS_CSV.encode())},
        timeout=30.0,
    )
    assert response.status_code == 200, response.text
    return api


@pytest.fixture(scope="session", autouse=True)
def _real_qa_stack():
    yield
    proc = _REAL.pop("proc", None)
    if proc is not None:
        proc.terminate()
        proc.wait(timeout=10)
    _REAL.clear()


def _ask(ctx: ScenarioContext, api: str, question: str) -> None:
    ctx.data = httpx.post(
        f"{api}/api/query", json={"question": question}, timeout=30.0
    ).json()
    ctx.qa_api = api  # type: ignore[attr-defined]


# --------------------------------------------------------------------------- #
# API-contract steps — real planner (AC-1..AC-6)
# --------------------------------------------------------------------------- #
@step(
    r"the analyst service is running with the real query planner "
    r'and the dataset "qa_orders"'
)
def given_real_service(ctx: ScenarioContext) -> None:
    api = _real_api()
    health = httpx.get(f"{api}/api/health").json()
    assert health["ok"] is True and health["qa"] == "real"
    names = {d["name"] for d in httpx.get(f"{api}/api/datasets").json()}
    # Feature 006 naming: the ingested dataset id now carries its extension.
    assert "qa_orders.csv" in names


@step(r'the user asks the planner "(?P<question>[^"]+)"')
def when_ask_planner(ctx: ScenarioContext, question: str) -> None:
    _ask(ctx, _REAL["api"], question)


@step(
    r"the user asks the planner a question whose generated SQL "
    r"references a column that does not exist"
)
def when_ask_planner_invalid(ctx: ScenarioContext) -> None:
    _ask(ctx, _REAL["api"], QUESTION_INVALID)


@step(r"a direct answer is returned carrying a summary and a trust trail")
def then_direct_answer(ctx: ScenarioContext) -> None:
    assert ctx.data["type"] == "answer", ctx.data
    assert not ctx.data.get("abstain"), ctx.data["summary"]
    assert ctx.data["summary"]
    trail = ctx.data["trustTrail"]
    assert trail is not None and trail["assumptions"] and trail["lineage"]
    assert trail["sql"]


@step(r'the answer reflects the locally computed total of "(?P<total>[^"]+)"')
def then_local_total(ctx: ScenarioContext, total: str) -> None:
    assert total in ctx.data["summary"], ctx.data["summary"]


@step(r"the trust trail discloses the SQL that was executed")
def then_sql_disclosed(ctx: ScenarioContext) -> None:
    assert "select" in ctx.data["trustTrail"]["sql"].lower()


@step(r"a clarification is returned offering the candidate region columns")
def then_clarification(ctx: ScenarioContext) -> None:
    assert ctx.data["type"] == "clarification", ctx.data
    assert len(ctx.data["options"]) >= 2
    assert any("region" in option.lower() for option in ctx.data["options"])


@step(r"the user answers the clarification with its first option")
def when_answer_clarification(ctx: ScenarioContext) -> None:
    payload = ctx.data
    assert payload["type"] == "clarification"
    choice = payload["options"][0]
    ctx.chosen = choice  # type: ignore[attr-defined]
    api = getattr(ctx, "qa_api", ctx.api)
    ctx.data = httpx.post(
        f"{api}/api/query/{payload['queryId']}/respond",
        json={"selectedOptions": [choice]},
        timeout=30.0,
    ).json()


@step(r"the trust trail SQL uses the chosen region column")
def then_sql_uses_choice(ctx: ScenarioContext) -> None:
    chosen: str = getattr(ctx, "chosen")
    column = chosen.split(" — ")[0].strip()
    assert column in ctx.data["trustTrail"]["sql"], (column, ctx.data)


@step(r"the service abstains from answering")
def then_abstains(ctx: ScenarioContext) -> None:
    assert ctx.data["type"] == "answer" and ctx.data.get("abstain") is True


@step(r"the abstention fabricates no chart and no SQL")
def then_no_fabrication(ctx: ScenarioContext) -> None:
    assert ctx.data["chartType"] == "none"
    assert not ctx.data.get("chartData")
    assert not ctx.data.get("trustTrail")


@step(r"a client checks that service's health")
def when_check_real_health(ctx: ScenarioContext) -> None:
    ctx.data = httpx.get(f"{_REAL['api']}/api/health").json()


@step(r'the health reports the Q&A engine "(?P<mode>[^"]+)"')
def then_health_qa_mode(ctx: ScenarioContext, mode: str) -> None:
    assert ctx.data["qa"] == mode, ctx.data


# --------------------------------------------------------------------------- #
# API-contract steps — fixtures mode (AC-6, AC-7)
# --------------------------------------------------------------------------- #
@step(r"the analyst service is running with mocked data")
def given_fixtures_service(ctx: ScenarioContext) -> None:
    health = httpx.get(f"{ctx.api}/api/health").json()
    assert health["ok"] is True and health["fixtures"] is True


@step(r"a client checks the fixtures service's health")
def when_check_fixtures_health(ctx: ScenarioContext) -> None:
    ctx.data = httpx.get(f"{ctx.api}/api/health").json()


@step(r'a client submits the canned question "(?P<question>[^"]+)"')
def when_canned_question(ctx: ScenarioContext, question: str) -> None:
    _ask(ctx, ctx.api, question)


# --------------------------------------------------------------------------- #
# Frontend-flow steps (AC-8..AC-10) — Playwright against the built app
# --------------------------------------------------------------------------- #
@step(r"the analyst app is open in a browser")
def given_app_open(ctx: ScenarioContext) -> None:
    expect = _expect()
    ctx.page.goto(_STACK["web"])
    expect(ctx.page.get_by_text("Semantic catalog").first).to_be_visible()


@step(r'the user asks in the chat "(?P<question>[^"]+)"')
def when_user_asks_chat(ctx: ScenarioContext, question: str) -> None:
    # Feature 006: the chat lives on the Query surface; the app opens on the
    # Ingest & Profile workbench, so switch to Query before asking.
    ctx.page.get_by_role("button", name="Query").click()
    box = ctx.page.get_by_placeholder("Ask across all tables")
    box.fill(question)
    box.press("Enter")


@step(r"the chat shows an abstention naming what the workspace covers")
def then_abstention_visible(ctx: ScenarioContext) -> None:
    expect = _expect()
    expect(
        ctx.page.get_by_text(
            "I can't answer that from the current catalog", exact=False
        ).first
    ).to_be_visible()
    expect(
        ctx.page.get_by_text("sales, customers and products", exact=False).first
    ).to_be_visible()


@step(r"the abstention shows no chart and no trust trail")
def then_no_chart_no_trail(ctx: ScenarioContext) -> None:
    expect = _expect()
    expect(ctx.page.get_by_text("Trust trail")).to_have_count(0)
    expect(ctx.page.locator("pre")).to_have_count(0)


@step(r'a stat answer appears showing the value "(?P<value>[^"]+)"')
def then_stat_answer(ctx: ScenarioContext, value: str) -> None:
    _expect()(ctx.page.get_by_text(value).first).to_be_visible()


@step(r"the trust trail is expandable down to the SQL")
def then_trail_expandable(ctx: ScenarioContext) -> None:
    expect = _expect()
    expect(ctx.page.get_by_text("Trust trail").first).to_be_visible()
    ctx.page.get_by_role("button", name="SQL", exact=True).click()
    expect(ctx.page.locator("pre").first).to_be_visible()


@step(r'a bar chart answer appears led by "(?P<leader>[^"]+)"')
def then_bar_answer(ctx: ScenarioContext, leader: str) -> None:
    expect = _expect()
    expect(ctx.page.get_by_text("Top 5 customers by revenue").first).to_be_visible()
    expect(ctx.page.get_by_text(leader).first).to_be_visible()


@step(r"the trust trail SQL reveals the join behind the chart")
def then_sql_reveals_join(ctx: ScenarioContext) -> None:
    expect = _expect()
    expect(ctx.page.get_by_text("Trust trail").first).to_be_visible()
    ctx.page.get_by_role("button", name="SQL", exact=True).click()
    expect(ctx.page.get_by_text("INNER JOIN", exact=False).first).to_be_visible()
