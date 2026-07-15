"""Local file exports — feature 014 (engine layer).

CSV/Parquet stream through DuckDB COPY; Excel streams through openpyxl's
write-only mode (deliberately NOT the DuckDB excel extension, which
downloads on first use — offline behavior must be identical, AC-11).
Exports are FULL-FIDELITY: the display cap is a UI protection, not a data
policy (AC-9), so queries re-run uncapped here. Everything is local;
nothing about an export ever crosses to a model.
"""

from __future__ import annotations

import os

from analyst.engine.sql_guard import assert_safe_select
from analyst.engine.store import DatasetStore, _quote_ident, _sql_str

FORMATS = ("csv", "parquet", "xlsx")


def export_dataset(
    store: DatasetStore, dataset: str, fmt: str, path: str | os.PathLike[str]
) -> None:
    """Export a whole dataset AS QUERIES SEE IT (the view — an approved
    normalization overlay included)."""
    if not store.exists(dataset):
        raise KeyError(dataset)
    export_query(store, f"SELECT * FROM {_quote_ident(dataset)}", fmt, path)


def export_query(
    store: DatasetStore, sql: str, fmt: str, path: str | os.PathLike[str]
) -> None:
    """Export a guarded SELECT's full result set to CSV/Parquet/Excel."""
    if fmt not in FORMATS:
        raise ValueError(f"Unsupported export format: {fmt!r} (use csv/parquet/xlsx)")
    with store._lock:  # same-layer access, like engine.query (M4 serialization)
        assert_safe_select(store._con, sql)
        if fmt == "csv":
            store._con.execute(
                f"COPY ({sql}) TO {_sql_str(str(path))} (FORMAT CSV, HEADER)"
            )
        elif fmt == "parquet":
            store._con.execute(
                f"COPY ({sql}) TO {_sql_str(str(path))} (FORMAT PARQUET)"
            )
        else:  # xlsx — openpyxl write-only streaming
            from openpyxl import Workbook

            cursor = store._con.execute(sql)
            columns = [d[0] for d in (cursor.description or ())]
            book = Workbook(write_only=True)
            sheet = book.create_sheet("export")
            sheet.append(columns)
            while True:
                rows = cursor.fetchmany(10_000)
                if not rows:
                    break
                for row in rows:
                    sheet.append(list(row))
            book.save(str(path))
