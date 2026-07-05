"""Feature 007 — within-DB Q&A: a connected database's tables become queryable
in the store's connection, so planner SQL executes against them (scanner
push-down), entirely locally."""

from __future__ import annotations

from pathlib import Path

import pytest

from analyst.domain.connection import ConnectionSpec, DatabaseEngine
from analyst.engine.query import run_select
from analyst.engine.store import DatasetStore

CHINOOK = Path(__file__).resolve().parents[1] / "golden" / "chinook.sqlite"


def _spec() -> ConnectionSpec:
    return ConnectionSpec(
        name="sales_db", engine=DatabaseEngine.SQLITE, path=str(CHINOOK)
    )


def test_connected_table_is_queryable_via_run_select(tmp_path):
    store = DatasetStore(base_dir=tmp_path)
    store.attach_database("sales_db", _spec(), ("Album", "Artist"))

    # the planner names a federated table by its dataset id "<conn>.<table>"
    result = run_select(store, 'SELECT COUNT(*) AS n FROM "sales_db.Album"')
    assert result.rows[0][0] > 0

    # a join across two connected tables (the 009 relationship case) also runs
    joined = run_select(
        store,
        'SELECT COUNT(*) AS n FROM "sales_db.Album" a '
        'JOIN "sales_db.Artist" r ON a.ArtistId = r.ArtistId',
    )
    assert joined.rows[0][0] > 0


def test_connected_tables_are_not_local_datasets(tmp_path):
    """Federated views are queryable but must not masquerade as local file
    datasets (they stay federated records in the repo)."""
    store = DatasetStore(base_dir=tmp_path)
    store.attach_database("sales_db", _spec(), ("Album",))
    assert "sales_db.Album" not in store.datasets()


def test_detach_removes_the_queryable_views(tmp_path):
    store = DatasetStore(base_dir=tmp_path)
    store.attach_database("sales_db", _spec(), ("Album",))
    store.detach_database("sales_db")
    try:
        run_select(store, 'SELECT COUNT(*) FROM "sales_db.Album"')
        raise AssertionError("view should be gone after detach")
    except Exception:
        pass


def test_within_db_qa_integration(tmp_path):
    """End-to-end wiring: connecting a scanner DB makes its tables db_queryable,
    included by the QA planner's table set, and runnable via the store."""
    from analyst.api.repository import StoreRepository
    from analyst.api.routes.databases import DatabaseManager
    from analyst.engine.query import run_select

    repo = StoreRepository(str(tmp_path / "data"))
    mgr = DatabaseManager(repo=repo)
    mgr.connect(_spec())

    recs = [r for r in repo.list_datasets() if r.name.startswith("sales_db.")]
    assert recs and all(r.federated and r.db_queryable for r in recs)

    # the planner's table set now includes the connected tables...
    from analyst.api.qa import PlannerQAService

    names = {
        t.name
        for t in PlannerQAService(planner=None)._tables(repo)  # type: ignore[arg-type]
    }
    assert "q_sales_db_Album" in names

    # ...and planner SQL over them actually runs against the source
    res = run_select(repo.store, 'SELECT COUNT(*) FROM "sales_db.Album"')
    assert res.rows[0][0] > 0


@pytest.mark.live
def test_real_nl_question_over_connected_db_answers_live(tmp_path):
    """Real flow (feature 007-fix), run on demand with `-m live`: a live NL
    question over a connected DB plans runnable SQL and answers — the exact path
    that abstained before the dot-free-alias fix. No cassette (federated sample
    ordering isn't deterministic enough to key one); this is the honest guard."""
    from analyst.agentic.claude_backend import ClaudeAgentBackend
    from analyst.agentic.gateway import LLMGateway
    from analyst.agentic.planner import QueryPlanner
    from analyst.api.qa import PlannerQAService
    from analyst.api.repository import StoreRepository
    from analyst.api.routes.databases import DatabaseManager

    repo = StoreRepository(str(tmp_path / "data"))
    DatabaseManager(repo=repo).connect(_spec())
    qa = PlannerQAService(QueryPlanner(LLMGateway(ClaudeAgentBackend())))
    res = qa.submit("How many albums does each artist have? Top 5 artists.", repo)
    assert not res.abstain, res.summary
    assert res.trust_trail and "q_sales_db_" in res.trust_trail.sql
