"""Local SQL execution helper (feature 003).

Executes planner SQL — ALREADY validated by the caller (closed-world,
SELECT-only; see analyst.domain.query_validation) — on the store's DuckDB
connection, entirely locally. Only a small, capped result set comes back;
bulk data never leaves the box (CHARTER §2 governance).

New engine module: intra-engine access to the store's connection keeps all
DuckDB access inside the data-engine layer without modifying the store.
"""

from __future__ import annotations

from analyst.domain.query import ResultTable
from analyst.engine.store import DatasetStore

MAX_RESULT_ROWS = 200


def run_select(
    store: DatasetStore, sql: str, max_rows: int = MAX_RESULT_ROWS
) -> ResultTable:
    """Run validated SELECT SQL locally; return a small, capped result set."""
    cursor = store._con.execute(sql)  # engine-internal (same layer)
    columns = tuple(d[0] for d in (cursor.description or ()))
    rows = cursor.fetchmany(max_rows + 1)
    return ResultTable(
        columns=columns,
        rows=tuple(tuple(row) for row in rows[:max_rows]),
        truncated=len(rows) > max_rows,
    )
