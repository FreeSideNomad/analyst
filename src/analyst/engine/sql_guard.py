"""Authoritative closed-world SQL gate (security review 2026-07-04, C2).

The domain-layer ``query_validation`` is a pure first-pass; THIS is the gate
that actually runs immediately before execution, using DuckDB's own parser so
it cannot be fooled by comments, quoting, or literal tricks.

Policy (deny by default):
- The statement must parse as exactly one SELECT (DuckDB's serializer errors on
  DDL/DML/ATTACH/COPY/PRAGMA/INSTALL and on stacked statements — those are
  rejected outright).
- Every base-table reference must resolve to a real view/table that already
  exists in the connection, or to a CTE defined in the query. A file path
  masquerading as a table (`FROM '/etc/x.csv'`) is not a real view → rejected.
- Table functions (`read_csv`, `read_parquet`, `read_text`, `glob`, …) are the
  ONLY way DuckDB reads a file, and none are allowed → rejected.

This closes the arbitrary-file-read bypass at the exact point of execution.
"""

from __future__ import annotations

import json
from typing import Any

import duckdb


class UnsafeQueryError(Exception):
    """Raised when SQL is not a safe, closed-world SELECT."""


def _walk(node: Any, base_tables: list[str], table_functions: list[str]) -> None:
    if isinstance(node, dict):
        node_type = node.get("type")
        if node_type == "BASE_TABLE":
            name = node.get("table_name")
            if isinstance(name, str):
                base_tables.append(name)
        elif node_type == "TABLE_FUNCTION":
            fn = node.get("function") or {}
            table_functions.append(fn.get("function_name") or "?")
        for value in node.values():
            _walk(value, base_tables, table_functions)
    elif isinstance(node, list):
        for item in node:
            _walk(item, base_tables, table_functions)


def _cte_names(node: Any, names: set[str]) -> None:
    """Collect CTE names (WITH x AS ...) so self-references are allowed."""
    if isinstance(node, dict):
        cte_map = node.get("cte_map")
        if isinstance(cte_map, dict):
            for entry in cte_map.get("map", []) or []:
                key = entry.get("key")
                if isinstance(key, str):
                    names.add(key.lower())
        for value in node.values():
            _cte_names(value, names)
    elif isinstance(node, list):
        for item in node:
            _cte_names(item, names)


def _existing_relations(con: duckdb.DuckDBPyConnection) -> set[str]:
    rows = con.execute("SELECT table_name FROM information_schema.tables").fetchall()
    return {str(r[0]).lower() for r in rows}


def assert_safe_select(con: duckdb.DuckDBPyConnection, sql: str) -> None:
    """Raise UnsafeQueryError unless ``sql`` is a safe closed-world SELECT."""
    try:
        serialized = con.execute("SELECT json_serialize_sql(?)", [sql]).fetchone()
    except duckdb.Error as exc:  # parser refused it entirely
        raise UnsafeQueryError("The query could not be parsed.") from exc
    if not serialized or not serialized[0]:
        raise UnsafeQueryError("The query could not be parsed.")

    ast = json.loads(serialized[0])
    if ast.get("error"):
        # DuckDB's serializer only accepts SELECT; everything else errors here.
        raise UnsafeQueryError("Only a single SELECT statement may execute.")
    statements = ast.get("statements") or []
    if len(statements) != 1:
        raise UnsafeQueryError("Exactly one SELECT statement may execute.")

    base_tables: list[str] = []
    table_functions: list[str] = []
    _walk(statements[0], base_tables, table_functions)

    if table_functions:
        raise UnsafeQueryError(
            f"Table functions are not permitted: {sorted(set(table_functions))}."
        )

    allowed = _existing_relations(con)
    ctes: set[str] = set()
    _cte_names(statements[0], ctes)
    allowed |= ctes

    for table in base_tables:
        if table.lower() not in allowed:
            raise UnsafeQueryError(f"Unknown or disallowed table source: {table}.")
