"""Feature 009 — relationship discovery: RI, join type, coverage, cross-source.

Synthetic tables built directly in DuckDB plus the golden Chinook SQLite,
covering AC-1 (declared), AC-2/5 (implied + evidence), AC-3/7 (RI rejection),
AC-4 (nullable → optional), AC-6 (cross-source).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import duckdb
import pytest

from analyst.domain.connection import ForeignKey, TableKeys
from analyst.domain.relationships import DECLARED, INFERRED, OPTIONAL, REQUIRED
from analyst.engine.profiler import profile_relation
from analyst.engine.relationships import DiscoverTable, discover

CHINOOK = Path(__file__).parent.parent / "golden" / "chinook.sqlite"


def _con() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(":memory:")


def _table(
    con: duckdb.DuckDBPyConnection, name: str, coldefs: str, rows: list[tuple]
) -> None:
    con.execute(f"CREATE TABLE {name} ({coldefs})")
    if rows:
        placeholders = ", ".join(["?"] * len(rows[0]))
        con.executemany(f"INSERT INTO {name} VALUES ({placeholders})", rows)


def _dt(
    con: duckdb.DuckDBPyConnection, name: str, keys: TableKeys | None = None
) -> DiscoverTable:
    return DiscoverTable(name=name, profile=profile_relation(con, name), keys=keys)


def _orders_customers(con: duckdb.DuckDBPyConnection, order_ids: list) -> None:
    _table(
        con, "customers", "id INTEGER, region VARCHAR", [(1, "N"), (2, "S"), (3, "E")]
    )
    _table(
        con,
        "orders",
        "order_id INTEGER, customer_id INTEGER",
        list(enumerate(order_ids, 1)),
    )


# --------------------------------------------------------------------------- #
# AC-2 / AC-5 — implied FK discovered, marked inferred with full coverage.
# --------------------------------------------------------------------------- #
def test_implied_fk_discovered_with_full_coverage():
    con = _con()
    _orders_customers(con, [1, 2, 3, 1, 2])
    rels = discover(con, [_dt(con, "orders"), _dt(con, "customers")])
    fk = [r for r in rels if r.child_table == "orders"]
    assert len(fk) == 1
    r = fk[0]
    assert (r.child_column, r.parent_table, r.parent_column) == (
        "customer_id",
        "customers",
        "id",
    )
    assert r.origin == INFERRED
    assert r.coverage == 1.0


# --------------------------------------------------------------------------- #
# AC-3 / AC-7 — a value absent from the parent key rejects the relationship.
# --------------------------------------------------------------------------- #
def test_ri_violation_rejects_relationship():
    con = _con()
    _orders_customers(con, [1, 2, 99])  # 99 has no matching customer
    rels = discover(con, [_dt(con, "orders"), _dt(con, "customers")])
    assert not [r for r in rels if r.child_table == "orders"]


def test_columns_sharing_name_but_not_values_not_linked():
    con = _con()
    _table(con, "products", "id INTEGER, name VARCHAR", [(1, "a"), (2, "b")])
    _table(con, "regions", "id INTEGER, name VARCHAR", [(10, "x"), (20, "y")])
    rels = discover(con, [_dt(con, "products"), _dt(con, "regions")])
    assert rels == []  # bare `id` is a PK name, never an FK child


# --------------------------------------------------------------------------- #
# AC-4 — nullable child → optional; fully-populated → required.
# --------------------------------------------------------------------------- #
def test_nullable_fk_is_optional():
    con = _con()
    _table(con, "customers", "id INTEGER", [(1,), (2,), (3,)])
    _table(
        con,
        "orders",
        "order_id INTEGER, customer_id INTEGER",
        [(1, 1), (2, None), (3, 2)],
    )
    rels = discover(con, [_dt(con, "orders"), _dt(con, "customers")])
    r = next(r for r in rels if r.child_table == "orders")
    assert r.join_type == OPTIONAL


def test_full_fk_is_required():
    con = _con()
    _orders_customers(con, [1, 2, 3])
    rels = discover(con, [_dt(con, "orders"), _dt(con, "customers")])
    r = next(r for r in rels if r.child_table == "orders")
    assert r.join_type == REQUIRED


# --------------------------------------------------------------------------- #
# AC-1 — declared single-column FK is lifted into a declared relationship.
# --------------------------------------------------------------------------- #
def test_declared_fk_is_surfaced():
    con = _con()
    _table(con, "customer", "customer_id INTEGER", [(1,), (2,)])
    _table(con, "rental", "rental_id INTEGER, customer_id INTEGER", [(1, 1), (2, 2)])
    keys = TableKeys(
        table="rental",
        foreign_keys=(ForeignKey(("customer_id",), "customer", ("customer_id",)),),
    )
    rels = discover(con, [_dt(con, "rental", keys=keys), _dt(con, "customer")])
    declared = [r for r in rels if r.origin == DECLARED]
    assert len(declared) == 1
    assert declared[0].parent_table == "customer"
    assert declared[0].child_column == "customer_id"


# --------------------------------------------------------------------------- #
# AC-6 — cross-source: a file column links to an attached DB table in one con.
# --------------------------------------------------------------------------- #
def test_cross_source_relationship(tmp_path):
    db = tmp_path / "src.sqlite"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE customer (customer_id INTEGER)")
    conn.executemany("INSERT INTO customer VALUES (?)", [(1,), (2,), (3,)])
    conn.commit()
    conn.close()

    con = _con()
    con.execute("INSTALL sqlite" if False else "SELECT 1")
    try:
        con.execute(f"ATTACH '{db}' AS ext (TYPE sqlite, READ_ONLY)")
    except duckdb.Error:
        pytest.skip("duckdb sqlite scanner unavailable")
    con.execute('CREATE VIEW customer AS SELECT * FROM ext.main."customer"')
    _table(
        con, "orders", "order_id INTEGER, customer_id INTEGER", [(1, 1), (2, 2), (3, 3)]
    )

    file_tbl = DiscoverTable("orders", profile_relation(con, "orders"))
    db_tbl = DiscoverTable(
        "customer", profile_relation(con, "customer"), relation='ext.main."customer"'
    )
    rels = discover(con, [file_tbl, db_tbl])
    cross = [
        r for r in rels if r.child_table == "orders" and r.parent_table == "customer"
    ]
    assert len(cross) == 1
    assert cross[0].origin == INFERRED


# --------------------------------------------------------------------------- #
# Chinook — declared FKs are real and validated end to end.
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(not CHINOOK.exists(), reason="chinook fixture missing")
def test_chinook_album_references_artist():
    con = _con()
    try:
        con.execute(f"ATTACH '{CHINOOK}' AS ck (TYPE sqlite, READ_ONLY)")
    except duckdb.Error:
        pytest.skip("duckdb sqlite scanner unavailable")
    con.execute('CREATE VIEW Album AS SELECT * FROM ck.main."Album"')
    con.execute('CREATE VIEW Artist AS SELECT * FROM ck.main."Artist"')
    album = DiscoverTable("Album", profile_relation(con, "Album"))
    artist = DiscoverTable("Artist", profile_relation(con, "Artist"))
    rels = discover(con, [album, artist])
    link = [r for r in rels if r.child_table == "Album" and r.parent_table == "Artist"]
    assert link, "Album.ArtistId → Artist should be inferred by RI"
    assert link[0].child_column == "ArtistId"


def _discover_two(
    tmp_path, child_csv, parent_csv, child="orders.csv", parent="customer.csv"
):
    from pathlib import Path

    from analyst.engine.store import DatasetStore
    from analyst.service.ingestion import IngestionService

    store = DatasetStore(tmp_path)
    svc = IngestionService(store)
    for name, content in ((child, child_csv), (parent, parent_csv)):
        p = Path(tmp_path) / name
        p.write_text(content)
        svc.ingest(p)
    return store.discover_relationships()


def test_inferred_fk_requires_a_unique_parent_key(tmp_path):
    """Review #4 (MED-HIGH): an inferred FK must target a UNIQUE parent column;
    a many-valued parent is not a key and must not be linked (would fan out joins)."""
    rels = _discover_two(
        tmp_path,
        "order_id,customer_id\n10,1\n11,2\n",
        "customer_id,name\n1,alice\n1,alice2\n2,bob\n",  # customer_id NOT unique
    )
    assert not any(
        r.child_column == "customer_id" and r.parent_table.startswith("customer")
        for r in rels
    ), rels


def test_inferred_fk_accepted_when_parent_is_unique(tmp_path):
    rels = _discover_two(
        tmp_path,
        "order_id,customer_id\n10,1\n11,2\n",
        "customer_id,name\n1,alice\n2,bob\n",  # unique
    )
    assert any(
        r.child_column == "customer_id" and r.parent_table.startswith("customer")
        for r in rels
    ), rels


def test_base_name_does_not_misclassify_ordinary_words():
    """Review #7: words ending in 'id' are not foreign keys; camelCase Id is."""
    from analyst.engine.relationships import _base_name

    assert _base_name("customer_id") == "customer"
    assert _base_name("ArtistId") == "artist"
    assert _base_name("CustomerID") == "customer"
    for word in ("paid", "valid", "void", "android", "ANDROID", "id"):
        assert _base_name(word) is None, word
