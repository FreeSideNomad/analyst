"""Feature 003 — closed-world SQL validation (AC-5, FR-13).

Pure domain logic: generated SQL must be a single SELECT statement referencing
only known datasets/columns before it may execute. Invalid SQL never runs.
"""

from analyst.domain.query_validation import validate_sql

TABLES = {
    "qa_orders": (
        "order_id",
        "customer",
        "billing_region",
        "ship_region",
        "amount",
        "order_date",
    ),
    "customers": ("customer_id", "customer_name", "region"),
}


def ok(sql: str) -> None:
    assert validate_sql(sql, TABLES) == []


def bad(sql: str, fragment: str) -> None:
    problems = validate_sql(sql, TABLES)
    assert problems, f"expected problems for: {sql}"
    assert any(fragment in p for p in problems), f"{fragment!r} not in {problems}"


# --------------------------------------------------------------------------- #
# Statement shape
# --------------------------------------------------------------------------- #
def test_plain_select_passes():
    ok("SELECT customer, amount FROM qa_orders")


def test_trailing_semicolon_is_tolerated():
    ok("SELECT amount FROM qa_orders;")


def test_multiple_statements_are_rejected():
    bad("SELECT amount FROM qa_orders; SELECT 1", "single")


def test_non_select_statements_are_rejected():
    bad("INSERT INTO qa_orders VALUES (1)", "SELECT")
    bad("UPDATE qa_orders SET amount = 0", "SELECT")
    bad("DROP TABLE qa_orders", "SELECT")


def test_forbidden_keywords_inside_a_select_are_rejected():
    bad("SELECT amount FROM qa_orders WHERE 1 IN (DELETE FROM qa_orders)", "DELETE")
    bad("WITH x AS (SELECT 1) SELECT * FROM x; ATTACH 'evil.db'", "single")
    # pragma functions are not catalog tables — rejected by the closed world
    bad("SELECT * FROM qa_orders UNION ALL SELECT * FROM pragma_show()", "pragma_show")


def test_empty_sql_is_rejected():
    bad("", "empty")
    bad("   ", "empty")


# --------------------------------------------------------------------------- #
# Closed-world tables
# --------------------------------------------------------------------------- #
def test_unknown_table_is_rejected():
    bad("SELECT amount FROM shipments", "shipments")


def test_join_between_known_tables_passes():
    ok(
        "SELECT c.customer_name, SUM(o.amount) AS total "
        "FROM qa_orders o INNER JOIN customers c ON o.customer = c.customer_id "
        "GROUP BY c.customer_name ORDER BY total DESC LIMIT 5"
    )


def test_cte_names_count_as_tables():
    ok(
        "WITH per_customer AS ("
        "  SELECT customer, SUM(amount) AS total FROM qa_orders GROUP BY customer"
        ") SELECT customer, total FROM per_customer ORDER BY total DESC"
    )


# --------------------------------------------------------------------------- #
# Closed-world columns
# --------------------------------------------------------------------------- #
def test_unknown_column_is_rejected():
    bad("SELECT profit FROM qa_orders", "profit")


def test_unknown_qualified_column_is_rejected():
    bad("SELECT o.profit FROM qa_orders o", "profit")


def test_unknown_qualifier_is_rejected():
    bad("SELECT z.amount FROM qa_orders o", "z")


def test_aliases_and_functions_are_not_flagged():
    ok(
        "SELECT billing_region, ROUND(SUM(amount), 2) AS total_amount "
        "FROM qa_orders WHERE amount IS NOT NULL "
        "GROUP BY billing_region ORDER BY total_amount DESC"
    )


def test_string_literals_and_comments_are_ignored():
    ok(
        "SELECT amount -- profit is not a column\n"
        "FROM qa_orders WHERE customer = 'nonexistent_column'"
    )


def test_quoted_identifiers_are_checked():
    ok('SELECT "amount" FROM "qa_orders"')
    bad('SELECT "profit" FROM "qa_orders"', "profit")


def test_star_and_qualified_star_pass():
    ok("SELECT * FROM qa_orders")
    ok("SELECT o.* FROM qa_orders o")


def test_cast_types_are_not_flagged():
    ok("SELECT CAST(amount AS DOUBLE) FROM qa_orders")
