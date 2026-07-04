"""Engine tests (feature 005) — federation connectors and service.

Deterministic and offline: the ATTACH path runs against the bundled Chinook
SQLite fixture; the bridge path runs against fake recorded drivers (dialect
SQL) plus a REAL stdlib-sqlite driver (end-to-end bridge machinery). No
Docker, no network.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from analyst.domain.connection import ConnectionSpec, DatabaseEngine
from analyst.domain.types import ColumnType
from analyst.engine.federation import (
    BridgeConnector,
    DuckDBAttachConnector,
    DuplicateConnectionError,
    FederationError,
    FederationService,
    SqliteBridgeDriver,
    UnknownConnectionError,
    create_connector,
    dialect_for,
)

CHINOOK = Path(__file__).resolve().parent.parent / "golden" / "chinook.sqlite"


@pytest.fixture
def chinook(tmp_path) -> Path:
    target = tmp_path / "chinook.sqlite"
    shutil.copy(CHINOOK, target)
    return target


def _sqlite_spec(path: Path, name: str = "chinook") -> ConnectionSpec:
    return ConnectionSpec(name=name, engine=DatabaseEngine.SQLITE, path=str(path))


# --------------------------------------------------------------------------- #
# ATTACH path (DuckDB sqlite scanner)
# --------------------------------------------------------------------------- #
def test_attach_lists_source_tables(chinook):
    con = DuckDBAttachConnector(_sqlite_spec(chinook))
    try:
        tables = con.tables()
        assert {"Album", "Artist", "Track", "Invoice"} <= set(tables)
    finally:
        con.close()


def test_attach_profiles_a_table_through_the_connection(chinook):
    con = DuckDBAttachConnector(_sqlite_spec(chinook))
    try:
        profile = con.profile("Album")
        assert profile.row_count == 53
        by_name = {c.name: c for c in profile.columns}
        assert by_name["AlbumId"].inferred_type is ColumnType.INTEGER
        assert by_name["Title"].inferred_type is ColumnType.TEXT
        assert by_name["AlbumId"].distinct_count == 53
        assert by_name["Title"].samples
    finally:
        con.close()


def test_attach_fetch_caps_result_size(chinook):
    con = DuckDBAttachConnector(_sqlite_spec(chinook))
    try:
        rows = con.fetch("Track", limit=10)
        assert len(rows) == 10
    finally:
        con.close()


def test_attach_reads_declared_keys(chinook):
    con = DuckDBAttachConnector(_sqlite_spec(chinook))
    try:
        keys = con.declared_keys()
        album = keys["Album"]
        assert album.primary_key == ("AlbumId",)
        fk = album.foreign_keys[0]
        assert fk.referenced_table == "Artist"
        assert fk.columns == ("ArtistId",)
        # composite PK survives
        assert set(keys["PlaylistTrack"].primary_key) == {"PlaylistId", "TrackId"}
    finally:
        con.close()


def test_attach_never_copies_source_data(chinook):
    before = {p.name for p in chinook.parent.iterdir()}
    con = DuckDBAttachConnector(_sqlite_spec(chinook))
    try:
        con.profile("Album")
        con.fetch("Album", limit=5)
    finally:
        con.close()
    after = {p.name for p in chinook.parent.iterdir()}
    assert after == before, "federation must not materialize source data"


def test_attach_unreachable_postgres_raises_a_clean_error():
    spec = ConnectionSpec(
        name="pg",
        engine=DatabaseEngine.POSTGRES,
        host="127.0.0.1",
        port=1,  # nothing listens here
        database="pagila",
        user="u",
        password="p",
    )
    with pytest.raises(FederationError):
        DuckDBAttachConnector(spec)


def test_attach_missing_sqlite_file_raises_a_clean_error(tmp_path):
    with pytest.raises(FederationError):
        DuckDBAttachConnector(_sqlite_spec(tmp_path / "absent.sqlite"))


# --------------------------------------------------------------------------- #
# Bridge path — dialect SQL (recorded fake drivers)
# --------------------------------------------------------------------------- #
class RecordingDriver:
    """Fake DB-API seam: records SQL, replays canned rows."""

    def __init__(self, replies: dict[str, list[tuple]]):
        self.replies = replies
        self.sql: list[str] = []
        self.closed = False

    def execute(self, sql: str) -> list[tuple]:
        self.sql.append(sql)
        for key, rows in self.replies.items():
            if key in sql:
                return rows
        return [(0, 0)]

    def close(self) -> None:
        self.closed = True


def test_mssql_dialect_pushes_down_with_top():
    assert "TOP 5" in dialect_for(DatabaseEngine.MSSQL).cap('SELECT * FROM "t"', 5)


def test_mssql_dialect_puts_top_after_distinct():
    capped = dialect_for(DatabaseEngine.MSSQL).cap('SELECT DISTINCT "c" FROM "t"', 5)
    assert capped.startswith("SELECT DISTINCT TOP 5 ")


def test_db2_dialect_pushes_down_with_fetch_first():
    capped = dialect_for(DatabaseEngine.DB2).cap('SELECT * FROM "t"', 5)
    assert "FETCH FIRST 5 ROWS ONLY" in capped


def test_bridge_lists_tables_via_dialect_sql():
    driver = RecordingDriver({"INFORMATION_SCHEMA.TABLES": [("Orders",), ("People",)]})
    con = BridgeConnector(
        _mssql_spec(), driver=driver, dialect=dialect_for(DatabaseEngine.MSSQL)
    )
    assert con.tables() == ("Orders", "People")


def _mssql_spec() -> ConnectionSpec:
    return ConnectionSpec(
        name="ms",
        engine=DatabaseEngine.MSSQL,
        host="h",
        database="Northwind",
        user="sa",
        password="x",
    )


def test_bridge_close_closes_the_driver():
    driver = RecordingDriver({})
    con = BridgeConnector(
        _mssql_spec(), driver=driver, dialect=dialect_for(DatabaseEngine.MSSQL)
    )
    con.close()
    assert driver.closed


# --------------------------------------------------------------------------- #
# Bridge path — REAL end-to-end over the stdlib sqlite driver
# --------------------------------------------------------------------------- #
def _sqlite_bridge(chinook) -> BridgeConnector:
    return BridgeConnector(
        _sqlite_spec(chinook),
        driver=SqliteBridgeDriver(str(chinook)),
        dialect=dialect_for(DatabaseEngine.SQLITE),
    )


def test_sqlite_bridge_lists_tables(chinook):
    con = _sqlite_bridge(chinook)
    try:
        assert {"Album", "Artist", "Track"} <= set(con.tables())
    finally:
        con.close()


def test_sqlite_bridge_profiles_by_pushdown(chinook):
    con = _sqlite_bridge(chinook)
    try:
        profile = con.profile("Album")
        assert profile.row_count == 53
        by_name = {c.name: c for c in profile.columns}
        assert by_name["AlbumId"].inferred_type is ColumnType.INTEGER
        assert by_name["AlbumId"].null_count == 0
        assert by_name["AlbumId"].distinct_count == 53
        assert by_name["AlbumId"].minimum is not None
        assert len(by_name["Title"].samples) <= 20
    finally:
        con.close()


def test_sqlite_bridge_reads_declared_keys(chinook):
    con = _sqlite_bridge(chinook)
    try:
        keys = con.declared_keys()
        assert keys["Album"].primary_key == ("AlbumId",)
        assert keys["Album"].foreign_keys[0].referenced_table == "Artist"
    finally:
        con.close()


def test_sqlite_bridge_fetch_caps_result_size(chinook):
    con = _sqlite_bridge(chinook)
    try:
        assert len(con.fetch("Track", limit=7)) == 7
    finally:
        con.close()


# --------------------------------------------------------------------------- #
# Factory + service
# --------------------------------------------------------------------------- #
def test_factory_picks_attach_for_sqlite_and_postgres(chinook):
    con = create_connector(_sqlite_spec(chinook))
    try:
        assert isinstance(con, DuckDBAttachConnector)
    finally:
        con.close()


def test_service_connects_and_reports_tables(chinook):
    service = FederationService()
    tables = service.connect(_sqlite_spec(chinook))
    names = {t.name for t in tables}
    assert {"Album", "Artist", "Track"} <= names
    album = next(t for t in tables if t.name == "Album")
    assert album.profile.row_count == 53
    assert album.keys is not None and album.keys.primary_key == ("AlbumId",)
    assert [s.name for s in service.list()] == ["chinook"]
    service.detach("chinook")
    assert service.list() == []


def test_service_rejects_duplicate_names(chinook):
    service = FederationService()
    service.connect(_sqlite_spec(chinook))
    with pytest.raises(DuplicateConnectionError):
        service.connect(_sqlite_spec(chinook))


def test_service_detach_unknown_raises(chinook):
    with pytest.raises(UnknownConnectionError):
        FederationService().detach("nope")


def test_service_fetch_is_capped_small(chinook):
    service = FederationService()
    service.connect(_sqlite_spec(chinook))
    rows = service.fetch("chinook", "Track", limit=3)
    assert len(rows) == 3
