"""Deterministic, set-based profiling computed in DuckDB (plan D1)."""

from __future__ import annotations

import duckdb

from analyst.domain.profile import ColumnProfile, DatasetProfile
from analyst.domain.types import ColumnType
from analyst.domain.types import from_duckdb_type

DEFAULT_SAMPLE_CAP = 20
NUMERIC_QUANTILES = (0.25, 0.5, 0.75)

# Narrower types a text column's values are tested against, most-specific first.
_MIXED_CANDIDATES = (
    (ColumnType.INTEGER, "BIGINT"),
    (ColumnType.DECIMAL, "DOUBLE"),
    (ColumnType.BOOLEAN, "BOOLEAN"),
    (ColumnType.DATE, "DATE"),
    (ColumnType.DATETIME, "TIMESTAMP"),
)
MIXED_MAJORITY = 0.5


def _detect_mixed(
    con: duckdb.DuckDBPyConnection,
    rel: str,
    col: str,
    non_null: int,
    sample_cap: int,
) -> tuple[ColumnType | None, tuple[object, ...]]:
    """If a text column is a majority-narrower-type with off-type stragglers,
    report (dominant_type, off_type_examples). Otherwise (None, ())."""
    if non_null <= 0:
        return None, ()
    for cand_type, cast_type in _MIXED_CANDIDATES:
        match = _fetch_row(
            con, f"SELECT COUNT(TRY_CAST({col} AS {cast_type})) FROM {rel}"
        )[0]
        if 0 < match < non_null and match >= MIXED_MAJORITY * non_null:
            off = con.execute(
                f"SELECT DISTINCT {col} FROM {rel} "
                f"WHERE {col} IS NOT NULL AND TRY_CAST({col} AS {cast_type}) IS NULL "
                f"LIMIT {int(sample_cap)}"
            ).fetchall()
            return cand_type, tuple(o[0] for o in off)
    return None, ()


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _fetch_row(con: duckdb.DuckDBPyConnection, sql: str) -> tuple:
    """Run a query expected to return exactly one row; never None."""
    row = con.execute(sql).fetchone()
    assert row is not None, "aggregate query returned no row"
    return row


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
    row_count = _fetch_row(con, f"SELECT COUNT(*) FROM {rel}")[0]

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
        agg = _fetch_row(con, f"SELECT {', '.join(select)} FROM {rel}")
        null_count, distinct_count = agg[0], agg[1]

        minimum = maximum = None
        quantiles: tuple[object, ...] = ()
        if is_numeric:
            minimum, maximum = agg[2], agg[3]
            quantiles = tuple(agg[4]) if agg[4] is not None else ()

        dominant_type = None
        off_type_examples: tuple[object, ...] = ()
        if inferred_type is ColumnType.TEXT:
            dominant_type, off_type_examples = _detect_mixed(
                con, rel, col, int(row_count) - int(null_count), sample_cap
            )

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
                is_mixed=dominant_type is not None,
                dominant_type=dominant_type,
                off_type_examples=off_type_examples,
            )
        )

    return DatasetProfile(row_count=int(row_count), columns=tuple(columns))
