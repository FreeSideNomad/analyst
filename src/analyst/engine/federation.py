"""Federation engine (feature 005) — relational DBs queried through, never copied.

Two connector paths behind one protocol:

- `DuckDBAttachConnector` — engines with a solid DuckDB scanner (SQLite,
  PostgreSQL): `ATTACH … (TYPE <engine>, READ_ONLY)` into a private in-memory
  DuckDB; profiling reuses the feature-001 `profile_relation` over the
  attached relation (a temp view), so the scanner pushes work to the source.
- `BridgeConnector` — engines without one (SQL Server via `pymssql`, IBM DB2
  via `ibm_db`): a thin DB-API seam pushes profiling SQL down to the source;
  only aggregates, capped samples and small result sets come back. A stdlib-
  `sqlite3` bridge driver doubles as the offline fallback for SQLite when the
  DuckDB extension can't load, and as the deterministic test double.

Governance: nothing here writes Parquet or copies tables; every result-set
entry point takes an explicit row cap.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Callable, Protocol

import duckdb

from analyst.domain.connection import (
    ConnectionSpec,
    DatabaseEngine,
    ForeignKey,
    TableKeys,
)
from analyst.domain.profile import ColumnProfile, DatasetProfile
from analyst.domain.types import ColumnType, from_duckdb_type
from analyst.engine.profiler import profile_relation

DEFAULT_SAMPLE_CAP = 20
DEFAULT_FETCH_CAP = 200


class FederationError(RuntimeError):
    """A connection/federation failure with a user-facing message."""


class DuplicateConnectionError(FederationError):
    pass


class UnknownConnectionError(FederationError):
    pass


class Connector(Protocol):
    """One connected source database, whichever path serves it."""

    def tables(self) -> tuple[str, ...]: ...
    def profile(self, table: str) -> DatasetProfile: ...
    def declared_keys(self) -> dict[str, TableKeys]: ...
    def fetch(self, table: str, limit: int = DEFAULT_FETCH_CAP) -> list[tuple]: ...
    def close(self) -> None: ...


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


# --------------------------------------------------------------------------- #
# ATTACH path — DuckDB scanners (sqlite, postgres)
# --------------------------------------------------------------------------- #
_ATTACH_ALIAS = "fed_src"

# The user-facing schema per scanner engine: attached catalogs also surface
# internal schemas (e.g. postgres information_schema/pg_catalog) — those are
# not user tables and must never become datasets.
_SOURCE_SCHEMAS = {
    DatabaseEngine.SQLITE: "main",
    DatabaseEngine.POSTGRES: "public",
}


class DuckDBAttachConnector:
    """ATTACH the source into a private in-memory DuckDB and query through."""

    def __init__(self, spec: ConnectionSpec):
        self.spec = spec
        self._con = duckdb.connect(":memory:")
        try:
            self._con.execute(self._attach_sql())
        except duckdb.Error as exc:
            self._con.close()
            raise FederationError(
                f"Could not connect to {spec.engine.label} database: {exc}"
            ) from exc

    def _attach_sql(self) -> str:
        spec = self.spec
        if spec.engine is DatabaseEngine.SQLITE:
            # DuckDB's sqlite ATTACH happily creates a missing file — reject
            # instead: connecting must never invent a database.
            from pathlib import Path

            if not Path(str(spec.path)).is_file():
                raise duckdb.IOException(f"SQLite database file not found: {spec.path}")
            source = str(spec.path)
        elif spec.engine is DatabaseEngine.POSTGRES:
            parts = [
                f"host={spec.host}",
                f"port={spec.resolved_port}",
                f"dbname={spec.database}",
                "connect_timeout=5",
            ]
            if spec.user:
                parts.append(f"user={spec.user}")
            if spec.password:
                parts.append(f"password={spec.password}")
            source = " ".join(parts)
        else:  # pragma: no cover - factory never routes others here
            raise FederationError(f"No DuckDB scanner for {spec.engine.label}.")
        literal = source.replace("'", "''")
        return (
            f"ATTACH '{literal}' AS {_ATTACH_ALIAS} "
            f"(TYPE {self.spec.engine.value}, READ_ONLY)"
        )

    def tables(self) -> tuple[str, ...]:
        if self.spec.engine is DatabaseEngine.POSTGRES:
            # Push down to the source: BASE TABLEs only. The scanner also
            # surfaces materialized views (possibly unpopulated) as tables.
            rows = self._con.execute(
                f"SELECT * FROM postgres_query({_ATTACH_ALIAS!r}, "
                "'SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = ''public'' AND table_type = ''BASE TABLE'' "
                "ORDER BY table_name')"
            ).fetchall()
        else:
            rows = self._con.execute(
                "SELECT table_name FROM duckdb_tables() "
                "WHERE database_name = ? AND schema_name = ? ORDER BY table_name",
                [_ATTACH_ALIAS, _SOURCE_SCHEMAS[self.spec.engine]],
            ).fetchall()
        return tuple(r[0] for r in rows)

    def _source_relation(self, table: str) -> str:
        schema = _SOURCE_SCHEMAS[self.spec.engine]
        return f"{_ATTACH_ALIAS}.{_quote(schema)}.{_quote(table)}"

    def profile(self, table: str) -> DatasetProfile:
        # profile_relation quotes its relation name as one identifier, so give
        # it a temp view over the attached (qualified) table — still fully
        # query-through: the view resolves into the scanner.
        self._con.execute(
            "CREATE OR REPLACE TEMP VIEW fed_profile_target AS "
            f"SELECT * FROM {self._source_relation(table)}"
        )
        return profile_relation(self._con, "fed_profile_target")

    def declared_keys(self) -> dict[str, TableKeys]:
        if self.spec.engine is DatabaseEngine.SQLITE:
            return _sqlite_declared_keys(str(self.spec.path))
        return self._postgres_declared_keys()

    def _postgres_declared_keys(self) -> dict[str, TableKeys]:
        rows = self._con.execute(
            f"SELECT * FROM postgres_query({_ATTACH_ALIAS!r}, "
            f"'{_PG_KEYS_SQL.replace(chr(39), chr(39) * 2)}')"
        ).fetchall()
        return _keys_from_rows([tuple(r) for r in rows])

    def fetch(self, table: str, limit: int = DEFAULT_FETCH_CAP) -> list[tuple]:
        return self._con.execute(
            f"SELECT * FROM {self._source_relation(table)} LIMIT {int(limit)}"
        ).fetchall()

    def close(self) -> None:
        self._con.close()


# --------------------------------------------------------------------------- #
# Declared keys — shared helpers
# --------------------------------------------------------------------------- #
def _sqlite_declared_keys(path: str) -> dict[str, TableKeys]:
    """PK/FK metadata via the stdlib driver (metadata only, read-only)."""
    uri = f"file:{path}?mode=ro"
    with sqlite3.connect(uri, uri=True) as con:
        tables = [
            r[0]
            for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        out: dict[str, TableKeys] = {}
        for table in tables:
            info = con.execute(f"PRAGMA table_info({_quote(table)})").fetchall()
            pk = tuple(r[1] for r in sorted(info, key=lambda r: r[5]) if r[5] > 0)
            fk_rows = con.execute(
                f"PRAGMA foreign_key_list({_quote(table)})"
            ).fetchall()
            grouped: dict[int, list[tuple]] = {}
            for row in fk_rows:  # (id, seq, ref_table, from, to, ...)
                grouped.setdefault(row[0], []).append(row)
            fks = tuple(
                ForeignKey(
                    columns=tuple(r[3] for r in sorted(rows_, key=lambda r: r[1])),
                    referenced_table=rows_[0][2],
                    referenced_columns=tuple(
                        r[4] for r in sorted(rows_, key=lambda r: r[1])
                    ),
                )
                for rows_ in grouped.values()
            )
            out[table] = TableKeys(table=table, primary_key=pk, foreign_keys=fks)
    return out


# Row shape shared by the information_schema/syscat key queries:
# (table, column, constraint_type 'PRIMARY KEY'|'FOREIGN KEY', seq,
#  referenced_table, referenced_column)
def _keys_from_rows(rows: list[tuple]) -> dict[str, TableKeys]:
    pk: dict[str, list[tuple[int, str]]] = {}
    fk: dict[tuple[str, str], list[tuple[int, str, str]]] = {}
    for table, column, ctype, seq, ref_table, ref_column in rows:
        if ctype == "PRIMARY KEY":
            pk.setdefault(table, []).append((int(seq), column))
        elif ctype == "FOREIGN KEY" and ref_table:
            fk.setdefault((table, ref_table), []).append((int(seq), column, ref_column))
    out: dict[str, TableKeys] = {}
    tables = {t for t in pk} | {t for t, _ in fk}
    for table in tables:
        fks = tuple(
            ForeignKey(
                columns=tuple(c for _, c, _ in sorted(cols)),
                referenced_table=ref_table,
                referenced_columns=tuple(rc for _, _, rc in sorted(cols)),
            )
            for (t, ref_table), cols in fk.items()
            if t == table
        )
        out[table] = TableKeys(
            table=table,
            primary_key=tuple(c for _, c in sorted(pk.get(table, []))),
            foreign_keys=fks,
        )
    return out


_PG_KEYS_SQL = """
SELECT tc.table_name, kcu.column_name, tc.constraint_type,
       kcu.ordinal_position,
       ccu.table_name AS ref_table, ccu.column_name AS ref_column
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON kcu.constraint_name = tc.constraint_name
 AND kcu.table_schema = tc.table_schema
LEFT JOIN information_schema.constraint_column_usage ccu
  ON ccu.constraint_name = tc.constraint_name
 AND ccu.table_schema = tc.table_schema
 AND tc.constraint_type = 'FOREIGN KEY'
WHERE tc.table_schema = 'public'
  AND tc.constraint_type IN ('PRIMARY KEY', 'FOREIGN KEY')
ORDER BY tc.table_name, tc.constraint_name, kcu.ordinal_position
"""


# --------------------------------------------------------------------------- #
# Bridge path — driver + dialect, query push-down
# --------------------------------------------------------------------------- #
class BridgeDriver(Protocol):
    """Minimal DB-API seam a bridge dialect speaks through."""

    def execute(self, sql: str) -> list[tuple]: ...
    def close(self) -> None: ...


@dataclass(frozen=True)
class BridgeDialect:
    """Engine-specific SQL for the bridge path (all executed at the source)."""

    cap: Callable[[str, int], str]  # wrap a SELECT with a row cap
    tables_sql: str
    columns_sql: Callable[[str], str]  # -> rows of (column_name, type_name)
    keys_sql: str | None  # rows shaped for _keys_from_rows; None = pragma path


def _cap_limit(sql: str, n: int) -> str:
    return f"{sql} LIMIT {int(n)}"


def _cap_top(sql: str, n: int) -> str:
    # T-SQL: TOP goes after DISTINCT (SELECT DISTINCT TOP n ...).
    if sql.startswith("SELECT DISTINCT "):
        return sql.replace("SELECT DISTINCT ", f"SELECT DISTINCT TOP {int(n)} ", 1)
    return sql.replace("SELECT ", f"SELECT TOP {int(n)} ", 1)


def _cap_fetch_first(sql: str, n: int) -> str:
    return f"{sql} FETCH FIRST {int(n)} ROWS ONLY"


_MSSQL_KEYS_SQL = """
SELECT tc.TABLE_NAME, kcu.COLUMN_NAME, tc.CONSTRAINT_TYPE,
       kcu.ORDINAL_POSITION, kcu2.TABLE_NAME AS REF_TABLE,
       kcu2.COLUMN_NAME AS REF_COLUMN
FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
  ON kcu.CONSTRAINT_NAME = tc.CONSTRAINT_NAME
LEFT JOIN INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc
  ON rc.CONSTRAINT_NAME = tc.CONSTRAINT_NAME
LEFT JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu2
  ON kcu2.CONSTRAINT_NAME = rc.UNIQUE_CONSTRAINT_NAME
 AND kcu2.ORDINAL_POSITION = kcu.ORDINAL_POSITION
WHERE tc.CONSTRAINT_TYPE IN ('PRIMARY KEY', 'FOREIGN KEY')
ORDER BY tc.TABLE_NAME, tc.CONSTRAINT_NAME, kcu.ORDINAL_POSITION
"""

_DB2_KEYS_SQL = """
SELECT k.TABNAME, k.COLNAME,
       CASE t.TYPE WHEN 'P' THEN 'PRIMARY KEY' ELSE 'FOREIGN KEY' END,
       k.COLSEQ, r.REFTABNAME,
       COALESCE(fk.REFCOLNAME, '')
FROM SYSCAT.KEYCOLUSE k
JOIN SYSCAT.TABCONST t
  ON t.CONSTNAME = k.CONSTNAME AND t.TABSCHEMA = k.TABSCHEMA
LEFT JOIN SYSCAT.REFERENCES r
  ON r.CONSTNAME = k.CONSTNAME AND r.TABSCHEMA = k.TABSCHEMA
LEFT JOIN LATERAL (
  SELECT kk.COLNAME AS REFCOLNAME
  FROM SYSCAT.KEYCOLUSE kk
  WHERE kk.CONSTNAME = r.REFKEYNAME AND kk.TABSCHEMA = r.REFTABSCHEMA
    AND kk.COLSEQ = k.COLSEQ
) fk ON 1 = 1
WHERE t.TYPE IN ('P', 'F') AND k.TABSCHEMA = CURRENT SCHEMA
ORDER BY k.TABNAME, k.CONSTNAME, k.COLSEQ
"""

_DIALECTS: dict[DatabaseEngine, BridgeDialect] = {
    DatabaseEngine.SQLITE: BridgeDialect(
        cap=_cap_limit,
        tables_sql=(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ),
        columns_sql=lambda t: f"PRAGMA table_info({_quote(t)})",
        keys_sql=None,  # pragma path (_sqlite_declared_keys)
    ),
    DatabaseEngine.MSSQL: BridgeDialect(
        cap=_cap_top,
        tables_sql=(
            "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_TYPE = 'BASE TABLE' ORDER BY TABLE_NAME"
        ),
        columns_sql=lambda t: (
            "SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS "
            f"WHERE TABLE_NAME = '{t}' ORDER BY ORDINAL_POSITION"  # noqa: S608
        ),
        keys_sql=_MSSQL_KEYS_SQL,
    ),
    DatabaseEngine.DB2: BridgeDialect(
        cap=_cap_fetch_first,
        tables_sql=(
            "SELECT TABNAME FROM SYSCAT.TABLES "
            "WHERE TABSCHEMA = CURRENT SCHEMA AND TYPE = 'T' ORDER BY TABNAME"
        ),
        columns_sql=lambda t: (
            "SELECT COLNAME, TYPENAME FROM SYSCAT.COLUMNS "
            f"WHERE TABNAME = '{t}' AND TABSCHEMA = CURRENT SCHEMA "  # noqa: S608
            "ORDER BY COLNO"
        ),
        keys_sql=_DB2_KEYS_SQL,
    ),
}


def dialect_for(engine: DatabaseEngine) -> BridgeDialect:
    return _DIALECTS[engine]


# Source type names → domain ColumnType (bridge path; scanner path uses
# from_duckdb_type). Unknown types fall back through from_duckdb_type → TEXT.
_SOURCE_TYPE_MAP = {
    "INT": ColumnType.INTEGER,
    "INT2": ColumnType.INTEGER,
    "INT4": ColumnType.INTEGER,
    "INT8": ColumnType.INTEGER,
    "MONEY": ColumnType.DECIMAL,
    "SMALLMONEY": ColumnType.DECIMAL,
    "BIT": ColumnType.BOOLEAN,
    "DATETIME2": ColumnType.DATETIME,
    "SMALLDATETIME": ColumnType.DATETIME,
    "DATETIMEOFFSET": ColumnType.DATETIME,
    "TIME": ColumnType.TEXT,
}


def _source_type(type_name: str) -> ColumnType:
    head = type_name.split("(", 1)[0].strip().upper()
    if head in _SOURCE_TYPE_MAP:
        return _SOURCE_TYPE_MAP[head]
    return from_duckdb_type(head)


class SqliteBridgeDriver:
    """Stdlib-sqlite BridgeDriver — offline fallback + deterministic test path."""

    def __init__(self, path: str):
        try:
            self._con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            self._con.execute("SELECT 1")
        except sqlite3.Error as exc:
            raise FederationError(f"Could not open SQLite database: {exc}") from exc
        self.path = path

    def execute(self, sql: str) -> list[tuple]:
        return self._con.execute(sql).fetchall()

    def close(self) -> None:
        self._con.close()


class BridgeConnector:
    """Query push-down through a Python driver; small results only."""

    def __init__(
        self,
        spec: ConnectionSpec,
        driver: BridgeDriver,
        dialect: BridgeDialect,
        sample_cap: int = DEFAULT_SAMPLE_CAP,
    ):
        self.spec = spec
        self._driver = driver
        self._dialect = dialect
        self._sample_cap = sample_cap

    def tables(self) -> tuple[str, ...]:
        return tuple(r[0] for r in self._driver.execute(self._dialect.tables_sql))

    def _columns(self, table: str) -> list[tuple[str, str]]:
        rows = self._driver.execute(self._dialect.columns_sql(table))
        if self.spec.engine is DatabaseEngine.SQLITE:
            return [(r[1], r[2]) for r in rows]  # PRAGMA table_info shape
        return [(r[0], r[1]) for r in rows]

    def profile(self, table: str) -> DatasetProfile:
        """Push profiling SQL down to the source; only aggregates return."""
        rel = _quote(table)
        row_count = int(self._driver.execute(f"SELECT COUNT(*) FROM {rel}")[0][0])  # noqa: S608
        columns: list[ColumnProfile] = []
        for name, type_name in self._columns(table):
            col = _quote(name)
            inferred = _source_type(type_name)
            numeric = inferred in (ColumnType.INTEGER, ColumnType.DECIMAL)
            select = [
                f"COUNT(*) - COUNT({col})",
                f"COUNT(DISTINCT {col})",
            ]
            if numeric:
                select += [f"MIN({col})", f"MAX({col})"]
            agg = self._driver.execute(
                f"SELECT {', '.join(select)} FROM {rel}"  # noqa: S608
            )[0]
            samples = self._driver.execute(
                self._dialect.cap(
                    f"SELECT DISTINCT {col} FROM {rel} WHERE {col} IS NOT NULL",  # noqa: S608
                    self._sample_cap,
                )
            )
            columns.append(
                ColumnProfile(
                    name=name,
                    inferred_type=inferred,
                    null_count=int(agg[0]),
                    distinct_count=int(agg[1]),
                    samples=tuple(s[0] for s in samples),
                    minimum=agg[2] if numeric else None,
                    maximum=agg[3] if numeric else None,
                    quantiles=(),
                )
            )
        return DatasetProfile(row_count=row_count, columns=tuple(columns))

    def declared_keys(self) -> dict[str, TableKeys]:
        if self._dialect.keys_sql is None:
            return _sqlite_declared_keys(str(self.spec.path))
        rows = self._driver.execute(self._dialect.keys_sql)
        return _keys_from_rows([tuple(r) for r in rows])

    def fetch(self, table: str, limit: int = DEFAULT_FETCH_CAP) -> list[tuple]:
        return self._driver.execute(
            self._dialect.cap(f"SELECT * FROM {_quote(table)}", limit)  # noqa: S608
        )

    def close(self) -> None:
        self._driver.close()


# --------------------------------------------------------------------------- #
# Driver factories (lazy imports — heavy drivers are the `dbs` extra)
# --------------------------------------------------------------------------- #
def _mssql_driver(spec: ConnectionSpec) -> BridgeDriver:
    try:
        import pymssql
    except ImportError as exc:  # pragma: no cover - environment-dependent
        raise FederationError(
            "SQL Server support needs the 'dbs' extra (uv sync --extra dbs)."
        ) from exc

    class _Driver:
        def __init__(self) -> None:
            try:
                self._con = pymssql.connect(
                    server=spec.host or "",
                    port=str(spec.resolved_port),
                    user=spec.user,
                    password=spec.password or "",
                    database=spec.database or "",
                    login_timeout=5,
                )
            except Exception as exc:
                raise FederationError(
                    f"Could not connect to SQL Server: {exc}"
                ) from exc

        def execute(self, sql: str) -> list[tuple]:
            cursor = self._con.cursor()
            cursor.execute(sql)
            return [tuple(r) for r in cursor.fetchall()]

        def close(self) -> None:
            self._con.close()

    return _Driver()


def _db2_driver(spec: ConnectionSpec) -> BridgeDriver:
    try:
        import ibm_db_dbi
    except ImportError as exc:  # pragma: no cover - environment-dependent
        raise FederationError(
            "IBM DB2 support needs the 'dbs' extra (uv sync --extra dbs)."
        ) from exc

    dsn = (
        f"DATABASE={spec.database};HOSTNAME={spec.host};"
        f"PORT={spec.resolved_port};PROTOCOL=TCPIP;"
        f"UID={spec.user};PWD={spec.password or ''};"
        "CONNECTTIMEOUT=5;"
    )

    class _Driver:
        def __init__(self) -> None:
            try:
                self._con = ibm_db_dbi.connect(dsn, "", "")
            except Exception as exc:
                raise FederationError(f"Could not connect to DB2: {exc}") from exc

        def execute(self, sql: str) -> list[tuple]:
            cursor = self._con.cursor()
            cursor.execute(sql)
            return [tuple(r) for r in cursor.fetchall()]

        def close(self) -> None:
            self._con.close()

    return _Driver()


# --------------------------------------------------------------------------- #
# Factory + service
# --------------------------------------------------------------------------- #
def create_connector(spec: ConnectionSpec) -> Connector:
    """Scanner where solid, bridge otherwise (see plan.md decision table)."""
    spec.validate()
    if spec.engine is DatabaseEngine.POSTGRES:
        return DuckDBAttachConnector(spec)
    if spec.engine is DatabaseEngine.SQLITE:
        try:
            return DuckDBAttachConnector(spec)
        except FederationError:
            # Extension unavailable (offline box) or scanner failure — the
            # stdlib bridge serves the same contract. A missing/corrupt file
            # fails there too, with a clean message.
            return BridgeConnector(
                spec,
                driver=SqliteBridgeDriver(str(spec.path)),
                dialect=dialect_for(DatabaseEngine.SQLITE),
            )
    if spec.engine is DatabaseEngine.MSSQL:
        return BridgeConnector(
            spec, driver=_mssql_driver(spec), dialect=dialect_for(spec.engine)
        )
    return BridgeConnector(
        spec, driver=_db2_driver(spec), dialect=dialect_for(spec.engine)
    )


@dataclass(frozen=True)
class FederatedTable:
    """What connecting yields per source table: live profile + declared keys."""

    name: str
    profile: DatasetProfile
    keys: TableKeys | None = None


@dataclass
class _Connection:
    spec: ConnectionSpec
    connector: Connector
    tables: tuple[FederatedTable, ...] = ()


ConnectorFactory = Callable[[ConnectionSpec], Connector]
# Module-scope aliases: inside the class body, `list` resolves to the `list`
# method, so annotations there must not name the builtin directly.
Rows = list[tuple]
Specs = list[ConnectionSpec]


class FederationService:
    """Registry of live connections; connect/profile/detach, all query-through."""

    def __init__(self, connector_factory: ConnectorFactory = create_connector):
        self._factory = connector_factory
        self._connections: dict[str, _Connection] = {}

    def connect(self, spec: ConnectionSpec) -> tuple[FederatedTable, ...]:
        if spec.name in self._connections:
            raise DuplicateConnectionError(
                f"A connection named '{spec.name}' already exists."
            )
        connector = self._factory(spec)
        try:
            keys = connector.declared_keys()
            tables = tuple(
                FederatedTable(
                    name=table,
                    profile=connector.profile(table),
                    keys=keys.get(table),
                )
                for table in connector.tables()
            )
        except Exception:
            connector.close()
            raise
        self._connections[spec.name] = _Connection(spec, connector, tables)
        return tables

    def list(self) -> Specs:
        return [c.spec for c in self._connections.values()]

    def tables(self, name: str) -> tuple[FederatedTable, ...]:
        return self._require(name).tables

    def fetch(self, name: str, table: str, limit: int = DEFAULT_FETCH_CAP) -> Rows:
        return self._require(name).connector.fetch(table, limit=limit)

    def detach(self, name: str) -> None:
        connection = self._require(name)
        connection.connector.close()
        del self._connections[name]

    def close(self) -> None:
        for name in list(self._connections):
            self.detach(name)

    def _require(self, name: str) -> _Connection:
        if name not in self._connections:
            raise UnknownConnectionError(f"No connection named '{name}'.")
        return self._connections[name]
