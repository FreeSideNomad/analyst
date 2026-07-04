"""Database-connection domain objects (feature 005) — pure, no I/O.

A `ConnectionSpec` is what the user provides (it carries the secret and never
leaves the server); a `ConnectionSummary` is its secret-free public view.
Declared PK/FK metadata (`TableKeys`) and the deterministic, LLM-free catalog
builder (`catalog_for_table`) live here so every engine layer produces the
same catalog shapes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from analyst.domain.catalog import CatalogEntry, ColumnDescription
from analyst.domain.profile import DatasetProfile
from analyst.domain.types import ColumnType


class DatabaseEngine(str, Enum):
    """The relational engines federation supports (human-specified)."""

    SQLITE = "sqlite"
    POSTGRES = "postgres"
    MSSQL = "mssql"
    DB2 = "db2"

    @property
    def label(self) -> str:
        return _ENGINE_LABELS[self]


_ENGINE_LABELS = {
    DatabaseEngine.SQLITE: "SQLite",
    DatabaseEngine.POSTGRES: "PostgreSQL",
    DatabaseEngine.MSSQL: "SQL Server",
    DatabaseEngine.DB2: "IBM DB2",
}

DEFAULT_PORTS = {
    DatabaseEngine.POSTGRES: 5432,
    DatabaseEngine.MSSQL: 1433,
    DatabaseEngine.DB2: 50000,
}

_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")


class InvalidConnectionError(ValueError):
    """A connection spec that cannot be attempted; message is user-facing."""


@dataclass(frozen=True)
class ConnectionSummary:
    """The public, secret-free view of a connection."""

    name: str
    engine: DatabaseEngine
    database: str | None = None
    host: str | None = None
    port: int | None = None
    user: str | None = None
    path: str | None = None


@dataclass(frozen=True)
class ConnectionSpec:
    """What the user provides to connect. `password` NEVER leaves the server."""

    name: str
    engine: DatabaseEngine
    path: str | None = None  # sqlite file
    host: str | None = None
    port: int | None = None
    database: str | None = None
    user: str | None = None
    password: str | None = None

    def validate(self) -> None:
        if not _NAME_RE.match(self.name or ""):
            raise InvalidConnectionError(
                "Connection name must start with a letter and contain only "
                "letters, digits, '_' or '-'."
            )
        if self.engine is DatabaseEngine.SQLITE:
            if not self.path:
                raise InvalidConnectionError(
                    "A SQLite connection needs a database file path."
                )
        else:
            if not self.host:
                raise InvalidConnectionError(
                    f"A {self.engine.label} connection needs a host."
                )
            if not self.database:
                raise InvalidConnectionError(
                    f"A {self.engine.label} connection needs a database name."
                )

    @property
    def resolved_port(self) -> int | None:
        if self.port is not None:
            return self.port
        return DEFAULT_PORTS.get(self.engine)

    def summary(self) -> ConnectionSummary:
        return ConnectionSummary(
            name=self.name,
            engine=self.engine,
            database=self.database,
            host=self.host,
            port=self.resolved_port,
            user=self.user,
            path=self.path,
        )


@dataclass(frozen=True)
class ForeignKey:
    """A declared foreign key: local columns → referenced table/columns."""

    columns: tuple[str, ...]
    referenced_table: str
    referenced_columns: tuple[str, ...]


@dataclass(frozen=True)
class TableKeys:
    """Declared key metadata for one source table."""

    table: str
    primary_key: tuple[str, ...] = ()
    foreign_keys: tuple[ForeignKey, ...] = ()


# --------------------------------------------------------------------------- #
# Deterministic catalog (no LLM): profile + declared keys → CatalogEntry
# --------------------------------------------------------------------------- #
_TYPE_ROLES = {
    ColumnType.INTEGER: ("measure", "Numeric column from the source table."),
    ColumnType.DECIMAL: ("measure", "Numeric column from the source table."),
    ColumnType.DATE: ("timestamp", "Date column from the source table."),
    ColumnType.DATETIME: ("timestamp", "Timestamp column from the source table."),
    ColumnType.BOOLEAN: ("category", "Boolean flag from the source table."),
    ColumnType.TEXT: ("text", "Text column from the source table."),
}


def catalog_for_table(
    table: str,
    engine_label: str,
    connection: str,
    profile: DatasetProfile,
    keys: TableKeys | None,
) -> CatalogEntry:
    """Build the deterministic catalog entry for a federated table.

    Declared keys are read into the catalog: PK columns become identifiers,
    FK columns name the table/column they reference. Everything else is
    described from its profiled type. No model call — the agentic cataloguer
    can enrich these later.
    """
    pk = set(keys.primary_key) if keys else set()
    fk_by_column: dict[str, tuple[str, str]] = {}
    if keys:
        for fk in keys.foreign_keys:
            for fk_col, ref_col in zip(fk.columns, fk.referenced_columns):
                fk_by_column[fk_col] = (fk.referenced_table, ref_col)

    columns: list[ColumnDescription] = []
    for col in profile.columns:
        role, description = _TYPE_ROLES.get(
            col.inferred_type, ("other", "Column from the source table.")
        )
        if col.name in pk and col.name in fk_by_column:
            ref_table, ref_col = fk_by_column[col.name]
            role = "identifier"
            description = (
                f"Primary key of {table} (declared); also a declared foreign "
                f"key referencing {ref_table}.{ref_col}."
            )
        elif col.name in pk:
            role = "identifier"
            description = f"Primary key of {table} (declared)."
        elif col.name in fk_by_column:
            ref_table, ref_col = fk_by_column[col.name]
            role = "identifier"
            description = f"Declared foreign key referencing {ref_table}.{ref_col}."
        columns.append(
            ColumnDescription(name=col.name, description=description, role=role)
        )

    return CatalogEntry(
        table_description=(
            f'Table "{table}" from the connected {engine_label} database '
            f'"{connection}" — federated: queried in place, never copied.'
        ),
        columns=tuple(columns),
        clarifications=(),
    )
