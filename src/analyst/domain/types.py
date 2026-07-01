"""Column type system — rich scalar types (CHARTER §3, AC-5)."""

from __future__ import annotations

from enum import Enum


class ColumnType(str, Enum):
    """The rich scalar types the profiler infers per column."""

    TEXT = "text"
    INTEGER = "integer"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"


# Mapping from DuckDB storage types to our domain ColumnType.
# Unlisted types fall back to TEXT (lossless).
_DUCKDB_TYPE_MAP = {
    "TINYINT": ColumnType.INTEGER,
    "SMALLINT": ColumnType.INTEGER,
    "INTEGER": ColumnType.INTEGER,
    "BIGINT": ColumnType.INTEGER,
    "HUGEINT": ColumnType.INTEGER,
    "UTINYINT": ColumnType.INTEGER,
    "USMALLINT": ColumnType.INTEGER,
    "UINTEGER": ColumnType.INTEGER,
    "UBIGINT": ColumnType.INTEGER,
    "FLOAT": ColumnType.DECIMAL,
    "DOUBLE": ColumnType.DECIMAL,
    "REAL": ColumnType.DECIMAL,
    "BOOLEAN": ColumnType.BOOLEAN,
    "DATE": ColumnType.DATE,
    "TIMESTAMP": ColumnType.DATETIME,
    "TIMESTAMP WITH TIME ZONE": ColumnType.DATETIME,
    "TIMESTAMP_NS": ColumnType.DATETIME,
    "DATETIME": ColumnType.DATETIME,
    "VARCHAR": ColumnType.TEXT,
}


def from_duckdb_type(duckdb_type: str) -> ColumnType:
    """Map a DuckDB column type name to a domain ColumnType.

    DECIMAL(p,s) and other parameterized types are normalized by their head.
    """
    head = duckdb_type.split("(", 1)[0].strip().upper()
    if head.startswith("DECIMAL") or head.startswith("NUMERIC"):
        return ColumnType.DECIMAL
    return _DUCKDB_TYPE_MAP.get(head, ColumnType.TEXT)
