"""Relationship discovery (feature 009) — local, governance-safe.

`discover(con, tables)` runs entirely inside one DuckDB connection: files
(parquet views) and connected-database tables (scanner views) are both just
relations there, so **cross-source discovery is uniform**. Nothing here calls
an LLM and no bulk rows leave DuckDB — only aggregate/set queries (AC-15).

Two sources of relationships:

- **Declared** — lifted from the source's own catalog (`TableKeys`), restricted
  the source's own catalog (`TableKeys`); single- OR multi-column
  (composite) keys. Coverage is 1.0 by definition.
- **Inferred** — single-column candidates proposed by a name heuristic
  (``orders.customer_id`` → ``customers.id`` / ``customer.customer_id``),
  constrained to a compatible type, then **validated by referential integrity**:
  every non-null child value must exist in the parent key set (a true subset).
  A name match that fails RI is dropped (AC-3, AC-7). ``join_type`` is
  ``optional`` when the child column has nulls, else ``required`` (AC-4).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import duckdb

from analyst.domain.connection import TableKeys
from analyst.domain.profile import DatasetProfile
from analyst.domain.relationships import (
    DECLARED,
    INFERRED,
    OPTIONAL,
    REQUIRED,
    Relationship,
)
from analyst.domain.types import ColumnType

_NUMERIC = {ColumnType.INTEGER, ColumnType.DECIMAL}


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


@dataclass(frozen=True)
class DiscoverTable:
    """A relation participating in discovery, queryable inside the connection.

    ``relation`` is the SQL that names it in ``con`` (defaults to the quoted
    table name — the common case where ``name`` is a view). Cross-source callers
    pass a scanner-backed relation (e.g. ``ext.main."customer"``).
    """

    name: str
    profile: DatasetProfile
    keys: TableKeys | None = None
    relation: str | None = None

    def sql(self) -> str:
        return self.relation or _quote(self.name)

    @property
    def columns(self) -> dict[str, ColumnType]:
        return {c.name: c.inferred_type for c in self.profile.columns}


@dataclass
class _Candidate:
    parent: DiscoverTable
    parent_column: str


def _types_compatible(a: ColumnType, b: ColumnType) -> bool:
    return a == b or (a in _NUMERIC and b in _NUMERIC)


def _base_name(column: str) -> str | None:
    """The referenced-entity stem of a plausible FK column, or None.

    ``customer_id`` → ``customer``; ``ArtistId`` → ``artist``. A bare ``id`` is a
    primary-key name, never an FK child. Review #7: an FK suffix is either the
    ``_id`` separator OR a capitalized ``Id``/``ID`` on a camelCase word — so
    ordinary lowercase words ending in ``id`` (``paid``, ``valid``, ``void``,
    ``android``) are NOT misread as foreign keys.
    """
    if column.lower().endswith("_id") and len(column) > 3:
        return column[:-3].lower()
    if (
        len(column) > 2
        and column[-2:] in ("Id", "ID")
        and column[-3].islower()  # camelCase boundary: artistId, not ANDROID
    ):
        return column[:-2].lower()
    return None


_FILE_EXTS = (".csv", ".tsv", ".json", ".xlsx", ".xls", ".parquet")


def _stem(name: str) -> str:
    """Drop a trailing file extension so a dataset id (``customers.csv``) matches
    an entity-derived base (``customer``)."""
    low = name.lower()
    for ext in _FILE_EXTS:
        if low.endswith(ext):
            return low[: -len(ext)]
    return low


def _name_matches_table(base: str, table: str) -> bool:
    t = _stem(table)
    # review #7: rstrip("s") stripped ALL trailing s ("class"->"clas"); depluralize
    # a single trailing 's' only.
    singular = t[:-1] if t.endswith("s") else t
    return t in {base, base + "s", base + "es"} or singular == base


def _candidate_parent_columns(
    base: str, child_column: str, parent: DiscoverTable
) -> list[str]:
    """Parent key columns a child FK could reference, most-specific first."""
    cols = parent.columns
    ordered: list[str] = []
    # declared single-column PK wins
    if parent.keys and len(parent.keys.primary_key) == 1:
        ordered.append(parent.keys.primary_key[0])
    for cand in (child_column, f"{base}_id", f"{base}id", "id", f"{base}_key"):
        for actual in cols:
            if actual.lower() == cand.lower() and actual not in ordered:
                ordered.append(actual)
    return ordered


def _child_columns(table: DiscoverTable) -> list[str]:
    return [c.name for c in table.profile.columns]


def _null_count(table: DiscoverTable, column: str) -> int:
    for c in table.profile.columns:
        if c.name == column:
            return c.null_count
    return 0


def _parent_is_unique_key(
    con: duckdb.DuckDBPyConnection, parent: DiscoverTable, parent_column: str
) -> bool:
    """A valid FK target must be a KEY — every non-null value unique (review #4).
    A many-valued parent column is not a key; linking to it would fan out joins
    and double-count aggregates."""
    pc = _quote(parent_column)
    row = con.execute(
        f"SELECT count({pc}), count(DISTINCT {pc}) FROM {parent.sql()}"
    ).fetchone()
    if not row:
        return False
    return int(row[0]) == int(row[1])


def _ri_holds(
    con: duckdb.DuckDBPyConnection,
    child: DiscoverTable,
    child_column: str,
    parent: DiscoverTable,
    parent_column: str,
) -> tuple[bool, float]:
    """(accepted, coverage): accepted iff every non-null child value is in the
    parent key set. Pure set query — no rows leave DuckDB (AC-15)."""
    cc, pc = _quote(child_column), _quote(parent_column)
    non_null = con.execute(
        f"SELECT count(*) FROM {child.sql()} WHERE {cc} IS NOT NULL"
    ).fetchone()
    total = int(non_null[0]) if non_null else 0
    if total == 0:
        return False, 0.0
    missing = con.execute(
        f"SELECT count(*) FROM {child.sql()} WHERE {cc} IS NOT NULL "
        f"AND {cc} NOT IN (SELECT {pc} FROM {parent.sql()} WHERE {pc} IS NOT NULL)"
    ).fetchone()
    missing_n = int(missing[0]) if missing else 0
    coverage = (total - missing_n) / total
    return missing_n == 0, coverage


def _declared(tables: list[DiscoverTable]) -> list[Relationship]:
    by_name = {t.name.lower(): t for t in tables}
    out: list[Relationship] = []
    for table in tables:
        if not table.keys:
            continue
        for fk in table.keys.foreign_keys:
            if not fk.columns or len(fk.columns) != len(fk.referenced_columns):
                continue
            child_col = fk.columns[0]
            # optional if ANY child key column is nullable (a null → no match)
            join_type = (
                OPTIONAL
                if any(_null_count(table, c) > 0 for c in fk.columns)
                else REQUIRED
            )
            parent = by_name.get(fk.referenced_table.lower())
            parent_name = parent.name if parent else fk.referenced_table
            out.append(
                Relationship(
                    child_table=table.name,
                    child_column=child_col,
                    parent_table=parent_name,
                    parent_column=fk.referenced_columns[0],
                    origin=DECLARED,
                    join_type=join_type,
                    coverage=1.0,
                    extra_columns=tuple(zip(fk.columns[1:], fk.referenced_columns[1:])),
                )
            )
    return out


def discover(
    con: duckdb.DuckDBPyConnection, tables: list[DiscoverTable]
) -> list[Relationship]:
    """All declared + validated-inferred single-column relationships."""
    declared = _declared(tables)
    declared_children = {(r.child_table, r.child_column) for r in declared}
    inferred: list[Relationship] = []

    for child in tables:
        child_types = child.columns
        for child_column in _child_columns(child):
            if (child.name, child_column) in declared_children:
                continue  # a declared FK is authoritative
            base = _base_name(child_column)
            if base is None:
                continue
            best: Relationship | None = None
            for parent in tables:
                if parent.name == child.name:
                    continue
                if not _name_matches_table(base, parent.name):
                    continue
                child_type = child_types[child_column]
                for parent_column in _candidate_parent_columns(
                    base, child_column, parent
                ):
                    if not _types_compatible(child_type, parent.columns[parent_column]):
                        continue
                    if not _parent_is_unique_key(con, parent, parent_column):
                        continue  # review #4: FK target must be a unique key
                    accepted, coverage = _ri_holds(
                        con, child, child_column, parent, parent_column
                    )
                    if not accepted:
                        continue
                    join_type = (
                        OPTIONAL if _null_count(child, child_column) > 0 else REQUIRED
                    )
                    candidate = Relationship(
                        child_table=child.name,
                        child_column=child_column,
                        parent_table=parent.name,
                        parent_column=parent_column,
                        origin=INFERRED,
                        join_type=join_type,
                        coverage=coverage,
                    )
                    # Best integrity match; ties broken deterministically by
                    # parent name so one link is chosen, not all (AC-7).
                    if best is None or (candidate.coverage, best.parent_table) > (
                        best.coverage,
                        candidate.parent_table,
                    ):
                        best = candidate
                    break  # first compatible key column of this parent
            if best is not None:
                inferred.append(best)

    return declared + inferred


def relationships_for(
    table: str, relationships: list[Relationship]
) -> tuple[Relationship, ...]:
    """The subset a given table participates in (as child or parent)."""
    return tuple(r for r in relationships if table in (r.child_table, r.parent_table))


@dataclass
class Workspace:
    """A set of relations gathered into one connection for discovery.

    Files register as views by construction; ``attach_source`` brings a
    connected database's tables in as scanner-backed views so cross-source FKs
    resolve in the same connection (AC-6).
    """

    con: duckdb.DuckDBPyConnection
    tables: list[DiscoverTable] = field(default_factory=list)

    def add(self, table: DiscoverTable) -> None:
        self.tables.append(table)

    def discover(self) -> list[Relationship]:
        return discover(self.con, self.tables)
