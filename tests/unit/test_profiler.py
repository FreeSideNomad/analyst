"""Unit tests for the deterministic profiler (Slice A)."""
import duckdb

from analyst.domain.types import ColumnType
from analyst.engine.profiler import profile_relation


def _con_with_table():
    con = duckdb.connect()
    con.execute(
        "CREATE TABLE t AS "
        "SELECT * FROM (VALUES (1, 'alice', 10.5), "
        "(2, 'bob', 20.0), "
        "(3, NULL, 30.25)) AS v(id, name, amount)"
    )
    return con


def test_reports_row_count():
    con = _con_with_table()
    prof = profile_relation(con, "t")
    assert prof.row_count == 3


def test_infers_rich_scalar_types():
    con = _con_with_table()
    prof = profile_relation(con, "t")
    types = {c.name: c.inferred_type for c in prof.columns}
    assert types["id"] == ColumnType.INTEGER
    assert types["name"] == ColumnType.TEXT
    assert types["amount"] == ColumnType.DECIMAL


def test_counts_nulls_per_column():
    con = _con_with_table()
    prof = profile_relation(con, "t")
    by_name = {c.name: c for c in prof.columns}
    assert by_name["name"].null_count == 1
    assert by_name["id"].null_count == 0


def test_reports_cardinality():
    con = _con_with_table()
    prof = profile_relation(con, "t")
    by_name = {c.name: c for c in prof.columns}
    assert by_name["id"].distinct_count == 3


def test_collects_sample_values_within_cap():
    con = _con_with_table()
    prof = profile_relation(con, "t", sample_cap=2)
    by_name = {c.name: c for c in prof.columns}
    assert 0 < len(by_name["id"].samples) <= 2
