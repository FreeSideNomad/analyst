"""Deterministic, set-based profiling computed in DuckDB (plan D1)."""
from __future__ import annotations

import duckdb

from analyst.domain.profile import ColumnProfile, DatasetProfile
from analyst.domain.types import ColumnType
from analyst.domain.types import from_duckdb_type

DEFAULT_SAMPLE_CAP = 20
NUMERIC_QUANTILES = (0.25, 0.5, 0.75)


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def profile_relation(
    con: duckdb.DuckDBPyConnection,
    relation: str,
    sample_cap: int = DEFAULT_SAMPLE_CAP,
) -> DatasetProfile:
    """Profile a registered DuckDB relation with deterministic statistics.

    Computes, per column: inferred type, null count, distinct count, and a
    capped set of sample values. Nothing here calls an LLM.
    """
    rel = _quote_ident(relation)
    row_count = con.execute(f"SELECT COUNT(*) FROM {rel}").fetchone()[0]

    quantile_list = "[" + ", ".join(str(q) for q in NUMERIC_QUANTILES) + "]"
    schema = con.execute(f"DESCRIBE {rel}").fetchall()
    columns: list[ColumnProfile] = []
    for row in schema:
        col_name, col_type = row[0], row[1]
        col = _quote_ident(col_name)
        inferred_type = from_duckdb_type(col_type)
        is_numeric = inferred_type in {ColumnType.INTEGER, ColumnType.DECIMAL}

        # One set-based aggregate query per column (plan D1 performance budget).
        select = [
            f"COUNT(*) - COUNT({col})",  # null_count
            f"COUNT(DISTINCT {col})",  # distinct_count
        ]
        if is_numeric:
            select += [
                f"MIN({col})",
                f"MAX({col})",
                f"quantile_cont({col}, {quantile_list})",
            ]
        agg = con.execute(f"SELECT {', '.join(select)} FROM {rel}").fetchone()
        null_count, distinct_count = agg[0], agg[1]

        minimum = maximum = None
        quantiles: tuple[object, ...] = ()
        if is_numeric:
            minimum, maximum = agg[2], agg[3]
            quantiles = tuple(agg[4]) if agg[4] is not None else ()

        samples = con.execute(
            f"SELECT DISTINCT {col} FROM {rel} "
            f"WHERE {col} IS NOT NULL LIMIT {int(sample_cap)}"
        ).fetchall()

        columns.append(
            ColumnProfile(
                name=col_name,
                inferred_type=inferred_type,
                null_count=int(null_count),
                distinct_count=int(distinct_count),
                samples=tuple(s[0] for s in samples),
                minimum=minimum,
                maximum=maximum,
                quantiles=quantiles,
            )
        )

    return DatasetProfile(row_count=int(row_count), columns=tuple(columns))
