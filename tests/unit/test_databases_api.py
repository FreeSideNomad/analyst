"""API tests (feature 005) — /api/databases connect/list/detach.

FastAPI TestClient over fixtures mode; the sample DB is the bundled Chinook
SQLite fixture (real federation, deterministic, offline).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from analyst.api.app import create_app
from analyst.api.repository import FixtureRepository

CHINOOK = Path(__file__).resolve().parent.parent / "golden" / "chinook.sqlite"


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(FixtureRepository()))


@pytest.fixture
def db_path(tmp_path) -> Path:
    target = tmp_path / "chinook.sqlite"
    shutil.copy(CHINOOK, target)
    return target


def _connect(client, db_path, name="chinook", **extra):
    payload = {"name": name, "engine": "sqlite", "path": str(db_path), **extra}
    return client.post("/api/databases/connect", json=payload)


# --------------------------------------------------------------------------- #
# AC-1 / AC-2 — connect exposes profiled, catalogued datasets
# --------------------------------------------------------------------------- #
def test_connect_registers_tables_as_datasets(client, db_path):
    response = _connect(client, db_path)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "chinook" and body["engine"] == "sqlite"
    assert {t["name"] for t in body["tables"]} >= {"Album", "Artist", "Track"}

    names = {d["name"] for d in client.get("/api/datasets").json()}
    assert {"chinook.Album", "chinook.Artist", "chinook.Track"} <= names


def test_connected_dataset_is_profiled_and_catalogued(client, db_path):
    _connect(client, db_path)
    ds = client.get("/api/datasets/chinook.Album").json()
    assert ds["rowCount"] == 53
    assert {c["name"] for c in ds["profile"]["columns"]} == {
        "AlbumId",
        "Title",
        "ArtistId",
    }
    assert ds["catalog"]["tableDescription"]
    roles = {c["name"]: c["role"] for c in ds["catalog"]["columns"]}
    assert roles["AlbumId"] == "identifier"


# --------------------------------------------------------------------------- #
# AC-3 — declared keys on the wire
# --------------------------------------------------------------------------- #
def test_declared_keys_are_reported(client, db_path):
    body = _connect(client, db_path).json()
    album = next(t for t in body["tables"] if t["name"] == "Album")
    assert album["primaryKey"] == ["AlbumId"]
    fk = album["foreignKeys"][0]
    assert fk["referencedTable"] == "Artist" and fk["columns"] == ["ArtistId"]


# --------------------------------------------------------------------------- #
# AC-4 — secrets never returned
# --------------------------------------------------------------------------- #
def test_no_response_ever_contains_the_password(client, db_path):
    secret = "s3cret-hunter2"
    connect_body = _connect(client, db_path, password=secret).text
    listing = client.get("/api/databases").text
    datasets = client.get("/api/datasets").text
    for payload in (connect_body, listing, datasets):
        assert secret not in payload
        assert "password" not in json.dumps(json.loads(payload)).lower()


# --------------------------------------------------------------------------- #
# AC-5 — list + detach
# --------------------------------------------------------------------------- #
def test_list_and_detach_removes_datasets(client, db_path):
    _connect(client, db_path)
    listed = client.get("/api/databases").json()
    assert [c["name"] for c in listed] == ["chinook"]

    assert client.delete("/api/databases/chinook").status_code == 204
    assert client.get("/api/databases").json() == []
    names = {d["name"] for d in client.get("/api/datasets").json()}
    assert not any(n.startswith("chinook.") for n in names)
    # seeded fixture datasets untouched
    assert {"sales", "customers", "products"} <= names


# --------------------------------------------------------------------------- #
# AC-6/7/8 — clean failures
# --------------------------------------------------------------------------- #
def test_unreachable_postgres_is_a_clean_client_error(client):
    response = client.post(
        "/api/databases/connect",
        json={
            "name": "pg",
            "engine": "postgres",
            "host": "127.0.0.1",
            "port": 1,
            "database": "pagila",
            "user": "u",
            "password": "p",
        },
    )
    assert 400 <= response.status_code < 500
    assert response.json()["detail"]


def test_duplicate_name_is_a_conflict(client, db_path):
    _connect(client, db_path)
    response = _connect(client, db_path)
    assert response.status_code == 409
    assert "chinook" in response.json()["detail"]


def test_detach_unknown_is_not_found(client):
    response = client.delete("/api/databases/nope")
    assert response.status_code == 404
    assert "nope" in response.json()["detail"]


def test_invalid_spec_is_a_client_error(client):
    response = client.post(
        "/api/databases/connect", json={"name": "x", "engine": "sqlite"}
    )
    assert response.status_code in (400, 422)


# --------------------------------------------------------------------------- #
# Reset seam — /api/_reset also resets connections (e2e isolation)
# --------------------------------------------------------------------------- #
def test_reset_clears_connections(client, db_path, monkeypatch):
    monkeypatch.setenv("ANALYST_FIXTURES", "1")
    _connect(client, db_path)
    assert client.get("/api/databases").json()
    client.post("/api/_reset")
    assert client.get("/api/databases").json() == []
    names = {d["name"] for d in client.get("/api/datasets").json()}
    assert not any(n.startswith("chinook.") for n in names)


def test_federated_tables_are_excluded_from_qa(tmp_path):
    """Connected-DB tables are catalogued but not offered to the Q&A planner
    (they're not locally queryable until 007/008) — so no un-runnable SQL."""
    from analyst.api.qa import PlannerQAService
    from analyst.api.repository import StoreRepository
    from analyst.domain.dataset import DatasetSummary
    from analyst.api.repository import DatasetRecord
    from analyst.domain.status import IngestionStatus

    repo = StoreRepository(str(tmp_path / "data"))
    repo.ingest("orders.csv", b"id,amount\n1,10\n2,20\n")
    # a federated record, as the DatabaseManager would add it
    fed = DatasetRecord(
        summary=DatasetSummary(
            name="pgsql.film", profile=repo.get_dataset("orders.csv").summary.profile
        ),
        file_name="pgsql.film",
        status=IngestionStatus.COMPLETE,
        federated=True,
    )
    repo.add_records([fed])
    # _tables presents dot-free SQL aliases (feature 007-fix); the not-yet-
    # queryable federated table (db_queryable=False, e.g. a bridge engine) is
    # still excluded so the planner never writes un-runnable SQL.
    names = {t.name for t in PlannerQAService.__new__(PlannerQAService)._tables(repo)}
    assert "q_orders_csv" in names
    assert "q_pgsql_film" not in names


# --------------------------------------------------------------------------- #
# Feature 010 — connect catalogues each table knowing the workspace (AC-1)
# --------------------------------------------------------------------------- #
def test_connect_catalogues_with_workspace_context(db_path):
    from analyst.api.routes.databases import DatabaseManager, _enrich_catalog_fn
    from analyst.domain.connection import ConnectionSpec, DatabaseEngine

    repo = FixtureRepository()  # seeded workspace: sales / customers / products
    seen = {}

    def spy(table, relationships, context):
        seen[table.name] = context
        return _enrich_catalog_fn(table, relationships, context)

    manager = DatabaseManager(repo=repo, catalog_fn=spy)
    manager.connect(
        ConnectionSpec(name="chinook", engine=DatabaseEngine.SQLITE, path=str(db_path))
    )
    manager._pool.shutdown(wait=True)  # drain the background cataloguing
    context = seen["Album"]
    assert context is not None
    names = {t.name for t in context.tables}
    # The pre-existing workspace tables, with their descriptions, are in view.
    assert "sales" in names
    assert context.describe("sales")


def test_connect_recatalogues_the_affected_existing_file(tmp_path):
    """AC-4 (connect path): an existing file learns it references a DB table."""
    import sqlite3

    from analyst.api.repository import StoreRepository
    from analyst.api.routes.databases import DatabaseManager
    from analyst.domain.connection import ConnectionSpec, DatabaseEngine

    repo = StoreRepository(str(tmp_path / "data"))
    repo.ingest(
        "orders.csv", b"order_id,customer_id,quantity\n1,10,2\n2,20,1\n3,10,3\n"
    )
    before = repo.get_dataset("orders.csv").summary.catalog.table_description
    assert "customers" not in before

    db = tmp_path / "crm.sqlite"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE customers (customer_id INTEGER PRIMARY KEY, region TEXT)")
    con.executemany(
        "INSERT INTO customers VALUES (?, ?)", [(10, "North"), (20, "South")]
    )
    con.commit()
    con.close()

    manager = DatabaseManager(repo=repo)
    manager.connect(
        ConnectionSpec(name="crm", engine=DatabaseEngine.SQLITE, path=str(db))
    )
    manager._pool.shutdown(wait=True)
    after = repo.get_dataset("orders.csv").summary.catalog.table_description
    assert "References crm.customers" in after


def _crm_sqlite(tmp_path, extra_column=False):
    import sqlite3

    db = tmp_path / "crm.sqlite"
    con = sqlite3.connect(db)
    cols = "customer_id INTEGER PRIMARY KEY, region TEXT" + (
        ", tier TEXT" if extra_column else ""
    )
    con.execute(f"CREATE TABLE customers ({cols})")
    rows = (
        [(10, "North", "gold"), (20, "South", "silver")]
        if extra_column
        else [
            (10, "North"),
            (20, "South"),
        ]
    )
    marks = "?, ?, ?" if extra_column else "?, ?"
    con.executemany(f"INSERT INTO customers VALUES ({marks})", rows)
    con.commit()
    con.close()
    return db


def test_connected_catalog_persists_and_is_reused_on_reconnect(tmp_path):
    """AC-6 + AC-7: the derived catalog survives a restart and reconnect uses
    it immediately — no re-derivation (a poisoned catalog_fn proves it)."""
    from analyst.api.repository import StoreRepository
    from analyst.api.routes.databases import DatabaseManager
    from analyst.domain.connection import ConnectionSpec, DatabaseEngine

    db = _crm_sqlite(tmp_path)
    spec = ConnectionSpec(name="crm", engine=DatabaseEngine.SQLITE, path=str(db))
    data = str(tmp_path / "data")

    repo = StoreRepository(data)
    manager = DatabaseManager(repo=repo)
    manager.connect(spec)
    manager._pool.shutdown(wait=True)
    derived = repo.get_dataset("crm.customers").summary.catalog
    assert "customer_id" in {c.name for c in derived.columns}
    manager.close()

    # Fresh session: reconnect must NOT re-derive (catalog_fn would blow up).
    def poisoned(table, relationships, context):
        raise AssertionError("re-derived a table whose schema did not change")

    repo2 = StoreRepository(data)
    manager2 = DatabaseManager(repo=repo2, catalog_fn=poisoned)
    manager2.connect(spec)
    if manager2._pool is not None:
        manager2._pool.shutdown(wait=True)
    record = repo2.get_dataset("crm.customers")
    assert record.catalog_status == "complete"
    assert record.summary.catalog == derived


def test_schema_change_on_reconnect_triggers_recataloguing(tmp_path):
    """AC-7: a changed schema is re-catalogued; the persisted entry is stale."""
    from analyst.api.repository import StoreRepository
    from analyst.api.routes.databases import DatabaseManager
    from analyst.domain.connection import ConnectionSpec, DatabaseEngine

    db = _crm_sqlite(tmp_path)
    spec = ConnectionSpec(name="crm", engine=DatabaseEngine.SQLITE, path=str(db))
    data = str(tmp_path / "data")

    repo = StoreRepository(data)
    manager = DatabaseManager(repo=repo)
    manager.connect(spec)
    manager._pool.shutdown(wait=True)
    manager.close()

    db.unlink()
    _crm_sqlite(tmp_path, extra_column=True)  # schema changed while down

    repo2 = StoreRepository(data)
    manager2 = DatabaseManager(repo=repo2)
    manager2.connect(spec)
    manager2._pool.shutdown(wait=True)
    record = repo2.get_dataset("crm.customers")
    assert record.catalog_status == "complete"
    assert "tier" in {c.name for c in record.summary.catalog.columns}


# --------------------------------------------------------------------------- #
# Feature 011 — sealed persistence + reconnect on restart
# --------------------------------------------------------------------------- #
def _spec_011(db):
    from analyst.domain.connection import ConnectionSpec, DatabaseEngine

    return ConnectionSpec(
        name="crm",
        engine=DatabaseEngine.SQLITE,
        path=str(db),
        user="reader",
        password="s3cret-pw",
    )


def _manager_011(tmp_path, passphrase):
    from analyst.api.repository import StoreRepository
    from analyst.api.routes.databases import DatabaseManager
    from analyst.engine.credentials import CredentialVault

    repo = StoreRepository(str(tmp_path / "data"))
    vault = CredentialVault(passphrase) if passphrase else None
    return repo, DatabaseManager(repo=repo, vault=vault)


def _drain(manager):
    if manager._pool is not None:
        manager._pool.shutdown(wait=True)
        manager._pool = None


def test_connect_with_vault_persists_and_restart_reconnects(tmp_path):
    """AC-1 + AC-2: remembered automatically; back after restart with its
    catalog immediately (010 reuse)."""
    db = _crm_sqlite(tmp_path)
    repo, manager = _manager_011(tmp_path, "k1")
    manager.connect(_spec_011(db))
    _drain(manager)
    manager.close()

    repo2, manager2 = _manager_011(tmp_path, "k1")
    manager2.restore_persisted()
    _drain(manager2)
    assert [s.name for s in manager2.list()] == ["crm"]
    record = repo2.get_dataset("crm.customers")
    assert record is not None
    assert record.catalog_status == "complete"  # persisted meaning, not re-derived


def test_detach_forgets_the_stored_credentials(tmp_path):
    """AC-5: after detach + restart, the connection does not reappear."""
    db = _crm_sqlite(tmp_path)
    _repo, manager = _manager_011(tmp_path, "k1")
    manager.connect(_spec_011(db))
    _drain(manager)
    manager.detach("crm")
    manager.close()

    _repo2, manager2 = _manager_011(tmp_path, "k1")
    manager2.restore_persisted()
    assert manager2.list() == []


def test_without_vault_nothing_persists(tmp_path):
    """AC-6: no key -> session-only, no vault file, nothing after restart."""
    db = _crm_sqlite(tmp_path)
    _repo, manager = _manager_011(tmp_path, None)
    manager.connect(_spec_011(db))
    _drain(manager)
    assert [s.name for s in manager.list()] == ["crm"]  # works for the session
    assert list((tmp_path / "data").glob("*.vault.json")) == []
    manager.close()

    _repo2, manager2 = _manager_011(tmp_path, None)
    manager2.restore_persisted()
    assert manager2.list() == []


def test_changed_key_requires_reentry_and_keeps_the_record(tmp_path):
    """AC-7: a different key -> no reconnect, no crash; the sealed record
    stays on disk so restoring the right key later revives it."""
    db = _crm_sqlite(tmp_path)
    _repo, manager = _manager_011(tmp_path, "k1")
    manager.connect(_spec_011(db))
    _drain(manager)
    manager.close()

    _repo2, manager2 = _manager_011(tmp_path, "k2")
    manager2.restore_persisted()  # must not raise
    assert manager2.list() == []
    manager2.close()

    _repo3, manager3 = _manager_011(tmp_path, "k1")  # right key restored
    manager3.restore_persisted()
    _drain(manager3)
    assert [s.name for s in manager3.list()] == ["crm"]


def test_unreachable_database_stays_visible_and_retryable(tmp_path):
    """AC-4: DB down at restart -> listed unreachable with its persisted
    catalog; retry re-attaches without re-entry once reachable."""
    db = _crm_sqlite(tmp_path)
    _repo, manager = _manager_011(tmp_path, "k1")
    manager.connect(_spec_011(db))
    _drain(manager)
    manager.close()

    hidden = tmp_path / "crm.hidden"
    db.rename(hidden)  # the database is unreachable while the service is down
    repo2, manager2 = _manager_011(tmp_path, "k1")
    manager2.restore_persisted()
    (schema,) = manager2.list()
    assert schema.name == "crm"
    assert schema.status == "unreachable"
    record = repo2.get_dataset("crm.customers")
    assert record is not None  # persisted meaning still visible
    assert record.summary.catalog is not None
    assert "customer_id" in {c.name for c in record.summary.catalog.columns}

    hidden.rename(db)  # reachable again
    manager2.reconnect("crm")
    _drain(manager2)
    (schema2,) = manager2.list()
    assert schema2.status == "connected"
    assert repo2.get_dataset("crm.customers").summary.profile.row_count == 2
