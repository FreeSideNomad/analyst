"""Step handlers for feature 017 — cross-database joins.

In-process seam: the synthetic sample kit's two SQLite databases connected
through the real DatabaseManager over a StoreRepository in the scenario
tmp_path. NL turns replay tests/cassettes/cross_db_planner.json (recorded
live once); the no-database abstention needs no model at all. "The app
restarts" rebuilds repository + manager with the persisted credentials
(feature 011), exactly as production boot does.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from acceptance.e2e_base import ScenarioContext, make_registry
from analyst.agentic.gateway import LLMGateway, LLMRequest, ReplayBackend
from analyst.agentic.planner import QueryPlanner
from analyst.api.qa import PlannerQAService
from analyst.api.repository import StoreRepository
from analyst.api.routes.databases import DatabaseManager
from analyst.domain.connection import ConnectionSpec, DatabaseEngine
from analyst.engine.credentials import CredentialVault
from scripts.make_cross_dbs import make as make_dbs

step, run_step = make_registry()

__all__ = ["ScenarioContext", "run_step"]

REPO_ROOT = Path(__file__).resolve().parent.parent
PLANNER_CASSETTE = str(REPO_ROOT / "tests" / "cassettes" / "cross_db_planner.json")
PASSPHRASE = "cross-db-acceptance-key"


class _SpyBackend:
    def __init__(self, inner: ReplayBackend, log: list):
        self.inner, self.log = inner, log

    def complete(self, request: LLMRequest) -> str:
        self.log.append(request)
        return self.inner.complete(request)


def _state(ctx: ScenarioContext) -> dict[str, Any]:
    if not isinstance(ctx.data, dict):
        ctx.data = {"exchanges": []}
    return ctx.data


def _service(ctx: ScenarioContext) -> PlannerQAService:
    state = _state(ctx)
    if "qa" not in state:
        state["qa"] = PlannerQAService(
            QueryPlanner(
                LLMGateway(
                    _SpyBackend(ReplayBackend(PLANNER_CASSETTE), state["exchanges"])
                )
            )
        )
    return state["qa"]


def _connect_both(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    os.environ["ANALYST_SECRET_KEY"] = PASSPHRASE
    crm, billing = make_dbs(ctx.tmp_path / "dbs")
    repo = StoreRepository(str(ctx.tmp_path / "data"))
    manager = DatabaseManager(repo, vault=CredentialVault(PASSPHRASE))
    for name, path in (("crm", crm), ("billing", billing)):
        manager.connect(
            ConnectionSpec(name=name, engine=DatabaseEngine.SQLITE, path=str(path))
        )
    _drain(repo)
    state.update(repo=repo, manager=manager)


def _drain(repo: StoreRepository) -> None:
    for _ in range(100):
        if all(r.catalog_status != "pending" for r in repo.list_datasets()):
            return
        time.sleep(0.1)


def _ask(ctx: ScenarioContext, question: str) -> None:
    state = _state(ctx)
    state["answer"] = _service(ctx).submit(question, state["repo"])


# --------------------------------------------------------------------------- #
# Givens
# --------------------------------------------------------------------------- #
@step(r"a connected CRM database and a connected billing database")
def given_both_connected(ctx: ScenarioContext) -> None:
    _connect_both(ctx)


@step(r"an operator key is configured")
def given_operator_key(ctx: ScenarioContext) -> None:
    assert os.environ.get("ANALYST_SECRET_KEY") == PASSPHRASE


@step(r"no database is connected")
def given_nothing_connected(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    state["repo"] = StoreRepository(str(ctx.tmp_path / "data"))


@step(r"the synthetic sample databases are generated twice")
def given_generated_twice(ctx: ScenarioContext) -> None:
    import sqlite3

    def dump(path: Path) -> list[str]:
        con = sqlite3.connect(path)
        lines = list(con.iterdump())
        con.close()
        return lines

    a1, b1 = make_dbs(ctx.tmp_path / "one")
    a2, b2 = make_dbs(ctx.tmp_path / "two")
    _state(ctx)["dumps"] = (dump(a1), dump(a2), dump(b1), dump(b2))


# --------------------------------------------------------------------------- #
# Whens
# --------------------------------------------------------------------------- #
@step(r"relationships are discovered across the workspace")
def when_discover(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    state["rels"] = state["repo"].store.discover_relationships(include_federated=True)


@step(r"the user asks which customer segment generates the most revenue")
def when_ask_segment(ctx: ScenarioContext) -> None:
    _ask(ctx, "Which customer segment generates the most revenue?")


@step(r"the user asks how many customers there are")
def when_ask_count(ctx: ScenarioContext) -> None:
    _ask(ctx, "How many customers are there?")


@step(r"the app restarts over the same data")
def when_restart(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    repo = StoreRepository(str(ctx.tmp_path / "data"))
    manager = DatabaseManager(repo, vault=CredentialVault(PASSPHRASE))
    manager.restore_persisted()
    _drain(repo)
    state.update(repo=repo, manager=manager)
    state.pop("qa", None)  # fresh service over the reborn repo


@step(r"the billing database is disconnected")
def when_detach_billing(ctx: ScenarioContext) -> None:
    _state(ctx)["manager"].detach("billing")


# --------------------------------------------------------------------------- #
# Thens
# --------------------------------------------------------------------------- #
@step(r"a relationship links billing invoices to CRM customers")
def then_cross_db_rel(ctx: ScenarioContext) -> None:
    rels = _state(ctx)["rels"]
    assert any(
        r.child_table == "billing.invoices"
        and r.child_column == "customer_id"
        and r.parent_table == "crm.customers"
        for r in rels
    ), [(r.child_table, r.parent_table) for r in rels]


@step(r'the answer shows "enterprise" leading at (?P<total>\d+)')
def then_enterprise_leads(ctx: ScenarioContext, total: str) -> None:
    answer = _state(ctx)["answer"]
    assert getattr(answer, "abstain", False) is False, answer.summary
    rows = {str(r[0]): float(r[1]) for r in answer.table.rows}
    assert rows.get("enterprise") == float(total), rows


@step(r"the answer's query names both the CRM and billing tables")
def then_query_names_both(ctx: ScenarioContext) -> None:
    sql = _state(ctx)["answer"].trust_trail.sql
    assert "crm.customers" in sql and "billing.invoices" in sql, sql


@step(r"the planning exchange carries only table metadata")
def then_exchange_metadata(ctx: ScenarioContext) -> None:
    exchanges = _state(ctx)["exchanges"]
    assert exchanges, "no planning exchange recorded"
    prompt = exchanges[-1].prompt
    assert "customers" in prompt and "invoices" in prompt


@step(r"the exchange carries no customer or invoice rows")
def then_exchange_no_rows(ctx: ScenarioContext) -> None:
    prompt = _state(ctx)["exchanges"][-1].prompt
    assert "Acme Corp,enterprise" not in prompt and "I1,C1" not in prompt


@step(r'asking the segment question again shows "enterprise" leading at (?P<total>\d+)')
def then_ask_again(ctx: ScenarioContext, total: str) -> None:
    when_ask_segment(ctx)
    then_enterprise_leads(ctx, total)


@step(r"the service abstains or reports plainly")
def then_abstains_or_plain(ctx: ScenarioContext) -> None:
    answer = _state(ctx)["answer"]
    assert (
        getattr(answer, "abstain", False) is True
        or "cannot" in str(getattr(answer, "summary", "")).lower()
    ), getattr(answer, "summary", answer)


@step(r"no answer is fabricated")
def then_no_fabrication(ctx: ScenarioContext) -> None:
    answer = _state(ctx)["answer"]
    assert getattr(answer, "chart_data", None) in (None, [])
    assert getattr(answer, "trust_trail", None) is None or not getattr(
        answer.trust_trail, "sql", ""
    )


@step(r"the answer is (?P<count>\d+) from the CRM database alone")
def then_count_from_crm(ctx: ScenarioContext, count: str) -> None:
    answer = _state(ctx)["answer"]
    assert getattr(answer, "abstain", False) is False
    value = answer.stat.value if answer.stat else str(answer.summary)
    assert count in str(value), value
    sql = answer.trust_trail.sql
    assert "crm.customers" in sql and "billing" not in sql, sql


@step(r"both runs produce identical databases")
def then_kit_identical(ctx: ScenarioContext) -> None:
    a1, a2, b1, b2 = _state(ctx)["dumps"]
    assert a1 == a2 and b1 == b2


@step(r"the documented totals hold: enterprise 150, smb 50")
def then_kit_totals(ctx: ScenarioContext) -> None:
    import sqlite3

    crm, billing = make_dbs(ctx.tmp_path / "totals")
    con = sqlite3.connect(billing)
    con.execute(f'ATTACH DATABASE "{crm}" AS crm')
    rows = dict(
        con.execute(
            "SELECT c.segment, SUM(i.amount) FROM invoices i "
            "JOIN crm.customers c ON c.customer_id = i.customer_id GROUP BY 1"
        ).fetchall()
    )
    con.close()
    assert rows == {"enterprise": 150.0, "smb": 50.0}


@step(r"the service abstains with a plain explanation")
def then_abstain_plain(ctx: ScenarioContext) -> None:
    _ask(ctx, "Which customer segment generates the most revenue?")
    answer = _state(ctx)["answer"]
    assert getattr(answer, "abstain", False) is True
    assert answer.summary
