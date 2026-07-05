"""Step handlers for feature 007 — within-DB Q&A (execution core).

Deterministic, in-process: a real StoreRepository + DatabaseManager connect the
Chinook golden SQLite; queryability, planner inclusion, execution, and detach
are asserted over the seam — no live model, no browser.
"""

from __future__ import annotations

from typing import Any

from acceptance.e2e_base import REPO_ROOT, ScenarioContext, make_registry

CHINOOK = REPO_ROOT / "tests" / "golden" / "chinook.sqlite"

step, run_step = make_registry()

__all__ = ["ScenarioContext", "run_step"]


def _state(ctx: ScenarioContext) -> dict[str, Any]:
    if not isinstance(ctx.data, dict):
        ctx.data = {}
    return ctx.data


@step(r'a workspace with the connected database "(?P<name>[^"]+)"')
def given_connected_db(ctx: ScenarioContext, name: str) -> None:
    from analyst.api.repository import StoreRepository
    from analyst.api.routes.databases import DatabaseManager
    from analyst.domain.connection import ConnectionSpec, DatabaseEngine

    repo = StoreRepository(str(ctx.tmp_path / "data"))
    mgr = DatabaseManager(repo=repo)
    mgr.connect(
        ConnectionSpec(name=name, engine=DatabaseEngine.SQLITE, path=str(CHINOOK))
    )
    _state(ctx).update(repo=repo, mgr=mgr)


@step(r'the table "(?P<dataset>[^"]+)" is marked queryable')
def then_marked_queryable(ctx: ScenarioContext, dataset: str) -> None:
    repo = _state(ctx)["repo"]
    rec = repo.get_dataset(dataset)
    assert rec is not None and rec.db_queryable, rec


@step(r'the planner\'s table set includes "(?P<dataset>[^"]+)"')
def then_planner_includes(ctx: ScenarioContext, dataset: str) -> None:
    from analyst.api.qa import PlannerQAService

    tables = PlannerQAService(planner=None)._tables(_state(ctx)["repo"])  # type: ignore[arg-type]
    assert dataset in {t.name for t in tables}


@step(r"the query '(?P<sql>.+)' is executed")
def when_execute(ctx: ScenarioContext, sql: str) -> None:
    from analyst.engine.query import run_select

    _state(ctx)["result"] = run_select(_state(ctx)["repo"].store, sql)


@step(r"a non-empty result is returned")
def then_non_empty(ctx: ScenarioContext) -> None:
    result = _state(ctx)["result"]
    assert result.rows and result.rows[0][0] > 0, result


@step(r'the database "(?P<name>[^"]+)" is disconnected')
def when_disconnect(ctx: ScenarioContext, name: str) -> None:
    _state(ctx)["mgr"].detach(name)


@step(r"the query '(?P<sql>.+)' can no longer run")
def then_cannot_run(ctx: ScenarioContext, sql: str) -> None:
    from analyst.engine.query import run_select

    try:
        run_select(_state(ctx)["repo"].store, sql)
        raise AssertionError("query should fail after disconnect")
    except AssertionError:
        raise
    except Exception:
        pass
