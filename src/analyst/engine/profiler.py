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

    schema = con.execute(f"DESCRIBE {rel}").fetchall()
    columns: list[ColumnProfile] = []
    for row in schema:
        col_name, col_type = row[0], row[1]
        col = _quote_ident(col_name)
        inferred_type = from_duckdb_type(col_type)
        null_count = con.execute(
            f"SELECT COUNT(*) - COUNT({col}) FROM {rel}"
        ).fetchone()[0]
        distinct_count = con.execute(
            f"SELECT COUNT(DISTINCT {col}) FROM {rel}"
        ).fetchone()[0]
        samples = con.execute(
            f"SELECT DISTINCT {col} FROM {rel} "
            f"WHERE {col} IS NOT NULL LIMIT {int(sample_cap)}"
        ).fetchall()
        minimum = None
        maximum = None
        quantiles: tuple[object, ...] = ()
        if inferred_type in {ColumnType.INTEGER, ColumnType.DECIMAL}:
            minimum, maximum = con.execute(
                f"SELECT MIN({col}), MAX({col}) FROM {rel}"
            ).fetchone()
            quantiles = tuple(
                con.execute(
                    f"SELECT quantile_cont({col}, {quantile}) FROM {rel}"
                ).fetchone()[0]
                for quantile in NUMERIC_QUANTILES
            )
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
