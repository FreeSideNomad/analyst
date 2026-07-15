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


def test_reports_numeric_distribution_statistics():
    con = _con_with_table()
    prof = profile_relation(con, "t")
    by_name = {c.name: c for c in prof.columns}
    amount = by_name["amount"]
    assert amount.minimum == 10.5
    assert amount.maximum == 30.25
    assert len(amount.quantiles) == 3


def test_non_numeric_columns_do_not_report_distribution_statistics():
    con = _con_with_table()
    prof = profile_relation(con, "t")
    by_name = {c.name: c for c in prof.columns}
    name = by_name["name"]
    assert name.minimum is None
    assert name.maximum is None
    assert name.quantiles == ()


def _con_with_mixed():
    con = duckdb.connect()
    con.execute(
        "CREATE TABLE m AS SELECT * FROM (VALUES "
        "('1'),('2'),('3'),('4'),('5'),('abc'),('def')) AS v(code)"
    )
    return con


def test_mixed_column_is_widened_to_text_and_recorded():
    prof = profile_relation(_con_with_mixed(), "m")
    code = next(c for c in prof.columns if c.name == "code")
    assert code.inferred_type == ColumnType.TEXT
    assert code.is_mixed is True
    assert code.dominant_type == ColumnType.INTEGER
    assert any("abc" == str(v) or "def" == str(v) for v in code.off_type_examples)


def test_pure_text_column_is_not_mixed():
    con = duckdb.connect()
    con.execute("CREATE TABLE t AS SELECT * FROM (VALUES ('alice'),('bob')) AS v(name)")
    prof = profile_relation(con, "t")
    name = next(c for c in prof.columns if c.name == "name")
    assert name.is_mixed is False
    assert name.dominant_type is None


def test_pure_numeric_column_is_not_mixed():
    prof = profile_relation(_con_with_table(), "t")
    ident = next(c for c in prof.columns if c.name == "id")
    assert ident.is_mixed is False


def test_real_distribution_numeric_histogram_and_categorical_topk(tmp_path):
    """Fix 5: distribution is REAL — numeric → histogram buckets summing to the
    non-null count; low-cardinality/text → top-K value frequencies."""
    import duckdb

    from analyst.engine.profiler import profile_relation

    con = duckdb.connect()
    con.execute(
        "CREATE TABLE t AS SELECT * FROM (VALUES "
        + ",".join(f"({i}, '{'gold' if i % 3 else 'silver'}')" for i in range(1, 61))
        + ") AS v(amount, tier)"
    )
    prof = profile_relation(con, "t")
    by = {c.name: c for c in prof.columns}
    # numeric 'amount' (60 distinct) → a histogram
    amt = by["amount"].distribution
    assert len(amt) >= 2
    assert sum(b.count for b in amt) == 60  # every non-null row is bucketed
    assert "–" in amt[0].label  # range label
    # low-cardinality 'tier' → value frequencies
    tier = {b.label: b.count for b in by["tier"].distribution}
    assert set(tier) == {"gold", "silver"}
    assert tier["gold"] + tier["silver"] == 60


def test_empty_column_has_no_distribution(tmp_path):
    import duckdb

    from analyst.engine.profiler import profile_relation

    con = duckdb.connect()
    con.execute("CREATE TABLE t AS SELECT NULL::INT AS x WHERE 1=0")
    prof = profile_relation(con, "t")
    assert prof.columns[0].distribution == ()


# --------------------------------------------------------------------------- #
# Defect 2026-07-15: columns literally named "v" or "c" shadowed the top-K
# distribution SQL's aliases (GROUP BY v bound to the real column) and broke
# profiling of the whole dataset. Aliases must be immune to column names.
# --------------------------------------------------------------------------- #
def test_columns_named_after_sql_aliases_profile_fine(tmp_path):
    import duckdb

    from analyst.engine.profiler import profile_relation

    con = duckdb.connect()
    con.execute("CREATE TABLE t (v VARCHAR, c VARCHAR, k VARCHAR)")
    con.execute("INSERT INTO t VALUES ('a','x','r1'), ('a','y','r2'), ('b','x','r3')")
    profile = profile_relation(con, "t")
    v = next(col for col in profile.columns if col.name == "v")
    assert v.distinct_count == 2
    bins = {b.label: b.count for b in v.distribution}
    assert bins == {"a": 2, "b": 1}
