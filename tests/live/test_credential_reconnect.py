"""LIVE test (feature 011) — connect Postgres → restart → auto-reconnect.

Deselected by default (`-m 'not live'`). Requires the pagila container:

    make dbs-up
    uv run pytest tests/live/test_credential_reconnect.py -m live -v
"""

from __future__ import annotations

import os
import socket

import pytest

from analyst.api.repository import StoreRepository
from analyst.api.routes.databases import DatabaseManager
from analyst.domain.connection import ConnectionSpec, DatabaseEngine
from analyst.engine.credentials import CredentialVault

pytestmark = pytest.mark.live

PG_HOST = os.environ.get("ANALYST_LIVE_PG_HOST", "localhost")
PG_PORT = int(os.environ.get("ANALYST_LIVE_PG_PORT", "55432"))


def _pg_available() -> bool:
    try:
        with socket.create_connection((PG_HOST, PG_PORT), timeout=2):
            return True
    except OSError:
        return False


@pytest.mark.skipif(not _pg_available(), reason="pagila Postgres not reachable")
def test_postgres_connect_restart_auto_reconnect(tmp_path):
    spec = ConnectionSpec(
        name="pg",
        engine=DatabaseEngine.POSTGRES,
        host=PG_HOST,
        port=PG_PORT,
        database=os.environ.get("ANALYST_LIVE_PG_DB", "pagila"),
        user=os.environ.get("ANALYST_LIVE_PG_USER", "postgres"),
        password=os.environ.get("ANALYST_LIVE_PG_PASSWORD", "analyst"),
    )
    data = str(tmp_path / "data")

    repo = StoreRepository(data)
    manager = DatabaseManager(repo=repo, vault=CredentialVault("live-key"))
    manager.connect(spec)
    manager._pool.shutdown(wait=True)
    before = {
        r.name: r.summary.catalog.table_description
        for r in repo.list_datasets()
        if r.federated
    }
    assert before, "no federated tables catalogued"
    manager.close()

    # "Restart": fresh stack over the same disk, same key — no re-entry.
    repo2 = StoreRepository(data)
    manager2 = DatabaseManager(repo=repo2, vault=CredentialVault("live-key"))
    manager2.restore_persisted()
    if manager2._pool is not None:
        manager2._pool.shutdown(wait=True)
    (schema,) = manager2.list()
    assert schema.name == "pg" and schema.status == "connected"
    after = {
        r.name: (r.summary.catalog.table_description, r.catalog_status)
        for r in repo2.list_datasets()
        if r.federated
    }
    assert set(after) == set(before)
    # 010 persisted meaning reused immediately — complete, not re-derived.
    for name, (description, status) in after.items():
        assert status == "complete"
        assert description == before[name]
    manager2.close()
