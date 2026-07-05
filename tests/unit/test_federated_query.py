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
    # trust trail shows the friendly dataset id (not the internal q_ alias)
    assert res.trust_trail and "sales_db." in res.trust_trail.sql


def test_trust_trail_shows_friendly_names_not_aliases(tmp_path):
    """Fix: the displayed SQL uses friendly dataset ids, not q_ aliases."""
    from analyst.api.qa import _friendly_sql
    from analyst.api.repository import StoreRepository

    repo = StoreRepository(str(tmp_path / "data"))
    repo.ingest("orders.csv", b"id,amount\n1,10\n2,20\n")
    alias = repo.store.register_query_alias("orders.csv")  # as _tables() does
    friendly = _friendly_sql(f"SELECT SUM(amount) FROM {alias}", repo)
    assert friendly == 'SELECT SUM(amount) FROM "orders.csv"'


def test_restart_leaves_no_dangling_federated_views(tmp_path):
    """Fix: attach uses TEMP views, so a connected DB leaves nothing queryable
    (and nothing in datasets()) after a restart — the user re-connects."""
    from analyst.api.repository import StoreRepository
    from analyst.api.routes.databases import DatabaseManager

    repo = StoreRepository(str(tmp_path / "data"))
    DatabaseManager(repo=repo).connect(_spec())
    reopened = StoreRepository(str(tmp_path / "data"))  # simulate a restart
    assert not any(n.startswith("sales_db.") for n in reopened.store.datasets())
    try:
        run_select(reopened.store, 'SELECT COUNT(*) FROM "sales_db.Album"')
        raise AssertionError("a federated view must not survive a restart")
    except AssertionError:
        raise
    except Exception:
        pass


def test_attach_failure_is_loud_and_disables_queryability(
    tmp_path, caplog, monkeypatch
):
    """Fix: a failed attach (e.g. missing scanner extension) is LOGGED, not
    swallowed; the connection stays catalogued but its tables are not queryable."""
    import logging

    from analyst.api.repository import StoreRepository
    from analyst.api.routes.databases import DatabaseManager

    repo = StoreRepository(str(tmp_path / "data"))
    mgr = DatabaseManager(repo=repo)

    def _boom(*_a, **_k):
        raise RuntimeError("no scanner extension available")

    monkeypatch.setattr(repo.store, "attach_database", _boom)
    with caplog.at_level(logging.WARNING):
        mgr.connect(_spec())
    assert any("within-DB Q&A disabled" in r.message for r in caplog.records)
    assert not any(r.db_queryable for r in repo.list_datasets() if r.federated)


@pytest.mark.live
def test_postgres_within_db_qa_live(tmp_path):
    """Real PostgreSQL path (run with `-m live` after `make dbs-up`): the pagila
    tables become queryable and run against the source."""
    from analyst.api.repository import StoreRepository
    from analyst.api.routes.databases import DatabaseManager
    from analyst.domain.connection import ConnectionSpec, DatabaseEngine

    repo = StoreRepository(str(tmp_path / "data"))
    spec = ConnectionSpec(
        name="pg",
        engine=DatabaseEngine.POSTGRES,
        host="localhost",
        port=55432,
        database="pagila",
        user="postgres",
        password="analyst",
    )
    DatabaseManager(repo=repo).connect(spec)
    recs = [r for r in repo.list_datasets() if r.federated]
    assert recs and all(r.db_queryable for r in recs)
    film = next(r.name for r in recs if r.name.endswith(".film"))
    res = run_select(repo.store, f'SELECT COUNT(*) FROM "{film}"')
    assert res.rows[0][0] > 0


def test_query_aliases_are_injective_under_collision(tmp_path):
    """Review #1 (CRITICAL): two dataset ids that mangle to the same q_ base must
    get distinct aliases, each returning its OWN data — never silently overwrite."""
    store = DatasetStore(base_dir=tmp_path)
    # "a.b" and "a_b" both mangle to base q_a_b
    store._con.execute('CREATE VIEW "a.b" AS SELECT 100 AS rev')
    store._con.execute('CREATE VIEW "a_b" AS SELECT 999 AS rev')
    a1 = store.register_query_alias("a.b")
    a2 = store.register_query_alias("a_b")
    assert a1 != a2, (a1, a2)
    assert store.alias_for("a.b") == a1  # stable
    assert run_select(store, f"SELECT rev FROM {a1}").rows[0][0] == 100
    assert run_select(store, f"SELECT rev FROM {a2}").rows[0][0] == 999


def test_bind_validation_accepts_valid_sql_and_rejects_unknowns(tmp_path):
    """Review #2: validation via DuckDB's real binder — valid function SQL
    (EXTRACT ... FROM, alias without AS) must NOT be rejected; unknown
    columns/tables must be. Never executes."""
    from analyst.api.repository import StoreRepository

    repo = StoreRepository(str(tmp_path / "data"))
    repo.ingest("orders.csv", b"order_date,amount\n2024-01-01,10\n2023-06-01,20\n")
    alias = repo.store.register_query_alias("orders.csv")
    ok = (
        f"SELECT EXTRACT(YEAR FROM order_date) y, SUM(amount) c FROM {alias} GROUP BY y"
    )
    assert repo.store.validation_problems(ok) == [], repo.store.validation_problems(ok)
    assert repo.store.validation_problems(f"SELECT profit FROM {alias}")  # unknown col
    assert repo.store.validation_problems("SELECT * FROM nope")  # unknown table
    assert repo.store.validation_problems(f"DELETE FROM {alias}")  # not a SELECT
