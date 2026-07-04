"""Engine-level SQL guard — the authoritative closed-world gate before
execution (security review 2026-07-04, CRITICAL C2).

Reproduces the confirmed arbitrary-file-read bypass, then locks the fix: the
planner's SQL is parsed via DuckDB's own parser and only base tables that are
real views/CTEs are allowed; table functions and file-path replacement scans
are rejected — regardless of comments, quoting, or literal-stripping tricks.
"""

import duckdb
import pytest

from analyst.engine.query import run_select
from analyst.engine.sql_guard import UnsafeQueryError, assert_safe_select
from analyst.engine.store import DatasetStore


@pytest.fixture
def store(tmp_path) -> DatasetStore:
    st = DatasetStore(str(tmp_path / "data"))
    src = tmp_path / "orders.csv"
    src.write_text("id,amount\n1,10\n2,20\n", encoding="utf-8")
    st.materialize_delimited("orders", src, ",")
    return st


def _secret_file(tmp_path) -> str:
    secret = tmp_path / "creds.csv"
    secret.write_text("key,value\napi,SUPER_SECRET\n", encoding="utf-8")
    return str(secret)


def test_C2_file_path_replacement_scan_is_blocked(store, tmp_path):
    """`SELECT * FROM '<file>'` must NOT read the file — it must be refused."""
    secret = _secret_file(tmp_path)
    with pytest.raises(UnsafeQueryError):
        run_select(store, f"SELECT * FROM '{secret}'")


def test_C2_table_function_read_csv_is_blocked(store, tmp_path):
    secret = _secret_file(tmp_path)
    with pytest.raises(UnsafeQueryError):
        run_select(store, f"SELECT * FROM read_csv('{secret}')")


def test_C2_read_text_table_function_is_blocked(store):
    with pytest.raises(UnsafeQueryError):
        run_select(store, "SELECT * FROM read_text('/etc/hostname')")


def test_C2_non_select_and_stacked_are_blocked(store):
    for sql in (
        "SELECT 1; DROP TABLE orders",
        "ATTACH 'evil.db'",
        "COPY orders TO '/tmp/x.csv'",
        "PRAGMA database_list",
    ):
        with pytest.raises(UnsafeQueryError):
            assert_safe_select(store._con, sql)


def test_C2_legitimate_queries_pass(store):
    # real views, CTEs, joins, aggregates, subqueries must still run
    assert run_select(store, "SELECT COUNT(*) FROM orders").rows == ((2,),)
    run_select(store, "WITH c AS (SELECT * FROM orders) SELECT SUM(amount) FROM c")
    run_select(
        store,
        "SELECT o.id FROM orders o WHERE o.amount IN (SELECT amount FROM orders)",
    )


def test_C2_unknown_base_table_is_blocked(store):
    con = duckdb.connect()  # not the store; 'orders' is unknown here
    with pytest.raises(UnsafeQueryError):
        assert_safe_select(con, "SELECT * FROM orders")
