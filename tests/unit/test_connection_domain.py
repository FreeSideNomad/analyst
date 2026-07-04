"""Domain tests (feature 005) — connection specs, keys, deterministic catalog."""

import pytest

from analyst.domain.catalog import CatalogEntry
from analyst.domain.connection import (
    ConnectionSpec,
    DatabaseEngine,
    ForeignKey,
    InvalidConnectionError,
    TableKeys,
    catalog_for_table,
)
from analyst.domain.profile import ColumnProfile, DatasetProfile
from analyst.domain.types import ColumnType


def _spec(**kw) -> ConnectionSpec:
    base = dict(name="chinook", engine=DatabaseEngine.SQLITE, path="/tmp/x.sqlite")
    base.update(kw)
    return ConnectionSpec(**base)


# --------------------------------------------------------------------------- #
# ConnectionSpec validation
# --------------------------------------------------------------------------- #
def test_engine_parses_from_wire_value():
    assert DatabaseEngine("postgres") is DatabaseEngine.POSTGRES
    assert DatabaseEngine("db2") is DatabaseEngine.DB2


def test_sqlite_spec_requires_a_path():
    with pytest.raises(InvalidConnectionError, match="path"):
        _spec(path=None).validate()


def test_server_spec_requires_host_and_database():
    spec = ConnectionSpec(name="pg", engine=DatabaseEngine.POSTGRES, host="localhost")
    with pytest.raises(InvalidConnectionError, match="database"):
        spec.validate()
    spec = ConnectionSpec(name="pg", engine=DatabaseEngine.POSTGRES, database="pagila")
    with pytest.raises(InvalidConnectionError, match="host"):
        spec.validate()


def test_connection_name_must_be_a_safe_slug():
    for bad in ("", "has space", 'we"ird', "a.b"):
        with pytest.raises(InvalidConnectionError, match="name"):
            _spec(name=bad).validate()
    _spec(name="prod_db-2").validate()  # ok


def test_default_ports_per_engine():
    assert (
        ConnectionSpec(
            name="pg", engine=DatabaseEngine.POSTGRES, host="h", database="d"
        ).resolved_port
        == 5432
    )
    assert (
        ConnectionSpec(
            name="ms", engine=DatabaseEngine.MSSQL, host="h", database="d", port=7777
        ).resolved_port
        == 7777
    )
    assert (
        ConnectionSpec(
            name="d2", engine=DatabaseEngine.DB2, host="h", database="d"
        ).resolved_port
        == 50000
    )


def test_summary_never_carries_the_password():
    spec = ConnectionSpec(
        name="pg",
        engine=DatabaseEngine.POSTGRES,
        host="h",
        database="d",
        user="u",
        password="s3cret",
    )
    summary = spec.summary()
    assert not hasattr(summary, "password")
    assert "s3cret" not in repr(summary)


# --------------------------------------------------------------------------- #
# Deterministic catalog from profile + declared keys (no LLM)
# --------------------------------------------------------------------------- #
def _profile() -> DatasetProfile:
    def col(name, ctype):
        return ColumnProfile(
            name=name,
            inferred_type=ctype,
            null_count=0,
            distinct_count=3,
            samples=(1, 2, 3),
        )

    return DatasetProfile(
        row_count=53,
        columns=(
            col("AlbumId", ColumnType.INTEGER),
            col("Title", ColumnType.TEXT),
            col("ArtistId", ColumnType.INTEGER),
        ),
    )


def test_catalog_for_table_marks_declared_keys():
    keys = TableKeys(
        table="Album",
        primary_key=("AlbumId",),
        foreign_keys=(
            ForeignKey(
                columns=("ArtistId",),
                referenced_table="Artist",
                referenced_columns=("ArtistId",),
            ),
        ),
    )
    entry = catalog_for_table("Album", "SQLite", "chinook", _profile(), keys)
    assert isinstance(entry, CatalogEntry)
    assert "federated" in entry.table_description.lower()
    assert "chinook" in entry.table_description
    by_name = {c.name: c for c in entry.columns}
    assert by_name["AlbumId"].role == "identifier"
    assert "primary key" in by_name["AlbumId"].description.lower()
    assert by_name["ArtistId"].role == "identifier"
    assert "Artist" in by_name["ArtistId"].description
    assert "foreign key" in by_name["ArtistId"].description.lower()


def test_catalog_for_table_describes_plain_columns_by_type():
    entry = catalog_for_table("Album", "SQLite", "chinook", _profile(), None)
    by_name = {c.name: c for c in entry.columns}
    assert by_name["Title"].role == "text"
    assert by_name["Title"].description
    assert by_name["AlbumId"].role != "identifier"  # no keys declared
