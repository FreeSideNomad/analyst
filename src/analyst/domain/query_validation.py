"""Closed-world SQL validation (feature 003, AC-5; FR-13).

Generated SQL is validated BEFORE execution: a single SELECT statement,
no data-modifying or environment-touching keywords, and every referenced
table/column must exist in the catalog (closed-world field validity — the
primary defence against schema hallucination). Pure string analysis; no I/O.

The checker is deliberately conservative: SQL it cannot account for is
rejected, and rejection means the SQL never executes (the caller abstains).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

# Statements/keywords that must never appear in planner SQL.
_FORBIDDEN = frozenset(
    {
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "CREATE",
        "ALTER",
        "TRUNCATE",
        "MERGE",
        "ATTACH",
        "DETACH",
        "COPY",
        "EXPORT",
        "IMPORT",
        "PRAGMA",
        "INSTALL",
        "LOAD",
        "CALL",
        "SET",
        "RESET",
        "GRANT",
        "REVOKE",
        "VACUUM",
        "CHECKPOINT",
        "USE",
        "EXECUTE",
        "PREPARE",
    }
)

# SQL vocabulary that legitimately appears as bare words in a SELECT.
_KEYWORDS = frozenset(
    {
        "SELECT",
        "FROM",
        "WHERE",
        "GROUP",
        "BY",
        "ORDER",
        "HAVING",
        "LIMIT",
        "OFFSET",
        "AS",
        "ON",
        "AND",
        "OR",
        "NOT",
        "NULL",
        "IS",
        "IN",
        "BETWEEN",
        "LIKE",
        "ILIKE",
        "CASE",
        "WHEN",
        "THEN",
        "ELSE",
        "END",
        "JOIN",
        "INNER",
        "LEFT",
        "RIGHT",
        "FULL",
        "OUTER",
        "CROSS",
        "UNION",
        "INTERSECT",
        "EXCEPT",
        "ALL",
        "ANY",
        "SOME",
        "DISTINCT",
        "ASC",
        "DESC",
        "WITH",
        "RECURSIVE",
        "EXISTS",
        "USING",
        "NULLS",
        "FIRST",
        "LAST",
        "TRUE",
        "FALSE",
        "INTERVAL",
        "FILTER",
        "OVER",
        "PARTITION",
        "ROWS",
        "RANGE",
        "PRECEDING",
        "FOLLOWING",
        "UNBOUNDED",
        "CURRENT",
        "ROW",
        # type names (CAST targets); harmless as bare words
        "INTEGER",
        "BIGINT",
        "SMALLINT",
        "TINYINT",
        "HUGEINT",
        "DOUBLE",
        "FLOAT",
        "REAL",
        "DECIMAL",
        "NUMERIC",
        "VARCHAR",
        "TEXT",
        "BOOLEAN",
        "DATE",
        "TIME",
        "TIMESTAMP",
        "DATETIME",
    }
)

_TOKEN = re.compile(r'"(?:[^"]|"")*"|[A-Za-z_][A-Za-z0-9_]*|\S')
_IDENT = re.compile(r'^(?:"(?:[^"]|"")*"|[A-Za-z_][A-Za-z0-9_]*)$')


def _strip_noise(sql: str) -> str:
    """Remove comments and string literals so only structure remains."""
    sql = re.sub(r"--[^\n]*", " ", sql)
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    sql = re.sub(r"'(?:[^']|'')*'", " '' ", sql)
    return sql


def _unquote(token: str) -> str:
    if token.startswith('"') and token.endswith('"'):
        return token[1:-1].replace('""', '"')
    return token


def _is_ident(token: str) -> bool:
    return bool(_IDENT.match(token)) and token.upper() not in _KEYWORDS


def validate_sql(sql: str, tables: Mapping[str, Sequence[str]]) -> list[str]:
    """Return the list of problems with planner SQL; empty means valid.

    ``tables`` is the closed world: dataset name -> its column names.
    """
    problems: list[str] = []
    stripped = _strip_noise(sql).strip()
    if not stripped:
        return ["The SQL statement is empty."]

    body = stripped.rstrip(";").strip()
    if ";" in body:
        return ["Only a single SQL statement may execute."]

    tokens = _TOKEN.findall(body)
    words = [t for t in tokens if _IDENT.match(t)]
    if not words or words[0].upper() not in {"SELECT", "WITH"}:
        problems.append("Only SELECT statements may execute.")
        return problems

    for token in words:
        if not token.startswith('"') and token.upper() in _FORBIDDEN:
            problems.append(f"Forbidden SQL keyword: {token.upper()}.")
    if problems:
        return problems

    known_tables = {name.lower() for name in tables}
    known_columns = {str(col).lower() for cols in tables.values() for col in cols}

    ctes: set[str] = set()
    aliases: set[str] = set()
    table_refs: list[str] = []

    # Pass 1 — structure: CTE names, FROM/JOIN targets and their aliases,
    # expression aliases (AS x), function names (ident followed by "(").
    functions: set[int] = set()
    for i, tok in enumerate(tokens):
        upper = tok.upper()
        if _is_ident(tok) and i + 1 < len(tokens) and tokens[i + 1] == "(":
            functions.add(i)
            continue
        if upper == "AS" and i + 1 < len(tokens) and _is_ident(tokens[i + 1]):
            nxt = tokens[i + 1]
            # "WITH name AS (" already names a CTE; other AS targets are aliases.
            aliases.add(_unquote(nxt).lower())
        if upper in {"WITH", ","}:
            # possible CTE head: <name> AS (
            if (
                i + 3 < len(tokens)
                and _is_ident(tokens[i + 1])
                and tokens[i + 2].upper() == "AS"
                and tokens[i + 3] == "("
            ):
                ctes.add(_unquote(tokens[i + 1]).lower())
        if upper in {"FROM", "JOIN"} and i + 1 < len(tokens):
            target = tokens[i + 1]
            if _is_ident(target):
                table_refs.append(_unquote(target).lower())
                # trailing table alias: FROM t x | FROM t AS x
                j = i + 2
                if j < len(tokens) and tokens[j].upper() == "AS":
                    j += 1
                if j < len(tokens) and _is_ident(tokens[j]):
                    aliases.add(_unquote(tokens[j]).lower())

    for ref in table_refs:
        if ref not in known_tables and ref not in ctes:
            problems.append(f"Unknown table: {ref}.")

    qualifiers = known_tables | ctes | aliases

    # Pass 2 — every remaining identifier must resolve in the closed world.
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if not _is_ident(tok) or i in functions:
            i += 1
            continue
        name = _unquote(tok).lower()
        # qualified reference: q.col or q.*
        if i + 2 < len(tokens) and tokens[i + 1] == ".":
            if name not in qualifiers:
                problems.append(f"Unknown table or alias: {name}.")
            member = tokens[i + 2]
            if member != "*" and _IDENT.match(member):
                member_name = _unquote(member).lower()
                allowed = known_columns | aliases
                if name in tables and member_name not in {
                    str(c).lower() for c in tables[name]
                }:
                    problems.append(f"Unknown column: {name}.{member_name}.")
                elif name not in tables and member_name not in allowed:
                    problems.append(f"Unknown column: {member_name}.")
            i += 3
            continue
        # skip the member position of a qualified ref (handled above)
        if i >= 2 and tokens[i - 1] == ".":
            i += 1
            continue
        if (
            name not in known_columns
            and name not in known_tables
            and name not in ctes
            and name not in aliases
        ):
            problems.append(f"Unknown column: {name}.")
        i += 1

    # de-duplicate, preserving order
    return list(dict.fromkeys(problems))
