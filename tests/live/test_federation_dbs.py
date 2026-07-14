"""LIVE federation tests (feature 005) — real engines in Docker, real sample DBs.

Deselected by default (pytest addopts `-m 'not live'`). To run:

    sh scripts/dbs_up.sh                # start + seed the containers
    uv sync --extra dbs               # pymssql + ibm_db drivers
    uv run pytest tests/live -m live -v

Targets (see docker-compose.dbs.yml + the feature runbook):
    Postgres 16 + Pagila      → DuckDB ATTACH scanner path
    SQL Server 2022 + Northwind → pymssql bridge path (amd64 emulation on Mac)
    DB2 community + SAMPLE    → ibm_db bridge path (amd64-only; may not run)

Connection coordinates are env-overridable so the suite can also point at
externally provisioned databases.
"""

from __future__ import annotations

import os
import socket

import pytest

from analyst.domain.connection import ConnectionSpec, DatabaseEngine
from analyst.engine.federation import FederationError, create_connector

pytestmark = pytest.mark.live


def _reachable(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=2.0):
            return True
    except OSError:
        return False


def _require_up(host: str, port: int, what: str) -> None:
    if not _reachable(host, port):
        pytest.skip(
            f"{what} not reachable at {host}:{port} — run `sh scripts/dbs_up.sh`"
        )


# --------------------------------------------------------------------------- #
# PostgreSQL + Pagila — ATTACH scanner
# --------------------------------------------------------------------------- #
PG_HOST = os.environ.get("ANALYST_TEST_PG_HOST", "127.0.0.1")
PG_PORT = int(os.environ.get("ANALYST_TEST_PG_PORT", "55432"))


@pytest.fixture(scope="module")
def pagila():
    _require_up(PG_HOST, PG_PORT, "Postgres (pagila)")
    connector = create_connector(
        ConnectionSpec(
            name="pagila",
            engine=DatabaseEngine.POSTGRES,
            host=PG_HOST,
            port=PG_PORT,
            database="pagila",
            user="postgres",
            password="analyst",
        )
    )
    yield connector
    connector.close()


def test_pagila_tables(pagila):
    tables = pagila.tables()
    assert {"actor", "film", "customer", "rental"} <= set(tables)
    # only public-schema user tables — no information_schema/pg_catalog leakage
    assert not [t for t in tables if t.startswith(("_pg_", "pg_", "sql_"))], tables


def test_pagila_profile_pushes_through(pagila):
    profile = pagila.profile("actor")
    assert profile.row_count == 200
    names = {c.name for c in profile.columns}
    assert {"actor_id", "first_name", "last_name"} <= names


def test_pagila_declared_keys(pagila):
    keys = pagila.declared_keys()
    assert keys["actor"].primary_key == ("actor_id",)
    film_actor = keys["film_actor"]
    assert set(film_actor.primary_key) == {"actor_id", "film_id"}
    refs = {fk.referenced_table for fk in film_actor.foreign_keys}
    assert {"actor", "film"} <= refs


def test_pagila_fetch_is_capped(pagila):
    assert len(pagila.fetch("film", limit=25)) == 25


def test_pagila_wrong_password_fails_cleanly():
    _require_up(PG_HOST, PG_PORT, "Postgres (pagila)")
    with pytest.raises(FederationError):
        create_connector(
            ConnectionSpec(
                name="bad",
                engine=DatabaseEngine.POSTGRES,
                host=PG_HOST,
                port=PG_PORT,
                database="pagila",
                user="postgres",
                password="wrong",
            )
        )


# --------------------------------------------------------------------------- #
# SQL Server + Northwind — pymssql bridge
# --------------------------------------------------------------------------- #
MS_HOST = os.environ.get("ANALYST_TEST_MSSQL_HOST", "127.0.0.1")
MS_PORT = int(os.environ.get("ANALYST_TEST_MSSQL_PORT", "51433"))


@pytest.fixture(scope="module")
def northwind():
    pytest.importorskip("pymssql", reason="install with `uv sync --extra dbs`")
    _require_up(MS_HOST, MS_PORT, "SQL Server (Northwind)")
    connector = create_connector(
        ConnectionSpec(
            name="northwind",
            engine=DatabaseEngine.MSSQL,
            host=MS_HOST,
            port=MS_PORT,
            database="Northwind",
            user="sa",
            password="Analyst!Passw0rd",
        )
    )
    yield connector
    connector.close()


def test_northwind_tables(northwind):
    tables = northwind.tables()
    assert {"Orders", "Customers", "Products", "Employees"} <= set(tables)


def test_northwind_profile_pushes_down(northwind):
    profile = northwind.profile("Orders")
    assert profile.row_count == 830
    names = {c.name for c in profile.columns}
    assert {"OrderID", "CustomerID", "OrderDate", "Freight"} <= names


def test_northwind_declared_keys(northwind):
    keys = northwind.declared_keys()
    assert keys["Orders"].primary_key == ("OrderID",)
    refs = {fk.referenced_table for fk in keys["Orders"].foreign_keys}
    assert {"Customers", "Employees", "Shippers"} <= refs
    # composite PK survives information_schema round-trip
    assert set(keys["Order Details"].primary_key) == {"OrderID", "ProductID"}


def test_northwind_fetch_is_capped(northwind):
    assert len(northwind.fetch("Orders", limit=12)) == 12


# --------------------------------------------------------------------------- #
# IBM DB2 + SAMPLE — ibm_db bridge
# --------------------------------------------------------------------------- #
DB2_HOST = os.environ.get("ANALYST_TEST_DB2_HOST", "127.0.0.1")
DB2_PORT = int(os.environ.get("ANALYST_TEST_DB2_PORT", "50000"))


@pytest.fixture(scope="module")
def db2_sample():
    pytest.importorskip("ibm_db_dbi", reason="install with `uv sync --extra dbs`")
    _require_up(DB2_HOST, DB2_PORT, "DB2 (SAMPLE)")
    try:
        connector = create_connector(
            ConnectionSpec(
                name="sample",
                engine=DatabaseEngine.DB2,
                host=DB2_HOST,
                port=DB2_PORT,
                database="SAMPLE",
                user="db2inst1",
                password="analyst",
            )
        )
    except FederationError as exc:
        pytest.skip(f"DB2 reachable but not connectable: {exc}")
    yield connector
    connector.close()


def test_db2_tables(db2_sample):
    tables = db2_sample.tables()
    assert {"EMPLOYEE", "DEPARTMENT", "PROJECT"} <= set(tables)


def test_db2_profile_pushes_down(db2_sample):
    profile = db2_sample.profile("EMPLOYEE")
    assert profile.row_count > 0
    names = {c.name for c in profile.columns}
    assert {"EMPNO", "WORKDEPT", "SALARY"} <= names


def test_db2_declared_keys(db2_sample):
    keys = db2_sample.declared_keys()
    assert keys["EMPLOYEE"].primary_key == ("EMPNO",)
    refs = {fk.referenced_table for fk in keys["EMPLOYEE"].foreign_keys}
    assert "DEPARTMENT" in refs


def test_db2_fetch_is_capped(db2_sample):
    assert len(db2_sample.fetch("EMPLOYEE", limit=5)) == 5
