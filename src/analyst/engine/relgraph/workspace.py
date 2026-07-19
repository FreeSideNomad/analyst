"""The workspace bridge — feature 019. FIXED, COMMITTED CODE.

Turns what analyst already validated about a user's linked data — profiled
types, RI-checked relationships, time columns — into the engine's
DatasetSpec, and builds the training database straight from workspace
relations (uploaded parquet views and federated scanner views are both
just DuckDB-backed frames here). No LLM near any of this: structure is
derived, never authored. Owner decision: no hooks equivalent — data that
arrived through analyst is already decoded.

The generated spec's foreign keys are a SUBSET of the workspace's
validated relationships by construction — edges are never invented
(mutation-gated by the board).
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Sequence

import duckdb
import pandas as pd

from analyst.domain.profile import DatasetProfile
from analyst.domain.relationships import Relationship
from analyst.domain.types import ColumnType

from .builddb import db_path
from .errors import RelgraphError
from .registry import cache_root
from .schema import (
    ColumnSpec,
    DatasetSpec,
    ForeignKeySpec,
    TableSpec,
    validate_dataset_spec,
)

# Profiler types → the engine's spec vocabulary.
_TYPE_MAP = {
    ColumnType.TEXT: "string",
    ColumnType.INTEGER: "int",
    ColumnType.DECIMAL: "float",
    ColumnType.BOOLEAN: "bool",
    ColumnType.DATE: "date",
    ColumnType.DATETIME: "timestamp",
}

_FILE_EXT = re.compile(r"\.(csv|tsv|json|xlsx|xls|parquet)$", re.IGNORECASE)


def table_alias(dataset_name: str) -> str:
    """A spec-safe table name for a workspace dataset id
    (``berka_loan.csv`` → ``berka_loan``; ``crm.customers`` → ``crm_customers``)."""
    return _FILE_EXT.sub("", dataset_name).replace(".", "_")


def spec_from_workspace(
    tables: dict[str, DatasetProfile],
    relationships: Sequence[Relationship],
    *,
    name: str,
    val_cutoff: str,
    test_cutoff: str,
    time_columns: dict[str, str | None] | None = None,
) -> DatasetSpec:
    """Derive the engine spec from catalog facts. ``tables`` maps workspace
    dataset ids to their profiles; ``relationships`` are the validated 009
    links (only links whose BOTH ends are in ``tables`` are used — a
    subset, never an invention). ``time_columns`` optionally pins the
    time column per table; otherwise the first date/datetime column of a
    table is used (tables without one are static context)."""
    aliases = {ds: table_alias(ds) for ds in tables}
    chosen_time = time_columns or {}
    specs: dict[str, TableSpec] = {}
    for ds, profile in tables.items():
        columns = [
            ColumnSpec(c.name, _TYPE_MAP[c.inferred_type]) for c in profile.columns
        ]
        # Time columns are DECISIONS (a birth date is an attribute, not an
        # event time) — candidates are surfaced via time_candidates(); the
        # confirmed choice arrives here. Unpinned tables are static context.
        time_col = chosen_time.get(ds)
        pk = _primary_key(profile, relationships, ds, aliases)
        specs[aliases[ds]] = TableSpec(
            name=aliases[ds],
            file="",
            derived=True,  # no source file: built from workspace relations
            primary_key=pk,
            columns=columns,
            time_column=time_col,
            foreign_keys=[],
        )
    for rel in relationships:
        if rel.child_table not in aliases or rel.parent_table not in aliases:
            continue
        child = specs[aliases[rel.child_table]]
        if any(fk.column == rel.child_column for fk in child.foreign_keys):
            continue
        child.foreign_keys.append(
            ForeignKeySpec(
                column=rel.child_column,
                ref_table=aliases[rel.parent_table],
                ref_column=rel.parent_column,
            )
        )
    spec = DatasetSpec(
        name=name,
        root=cache_root() / "workspace" / name,
        val_timestamp=val_cutoff,
        test_timestamp=test_cutoff,
        sources=[],
        tables=specs,
    )
    validate_dataset_spec(spec)
    return spec


def _primary_key(
    profile: DatasetProfile,
    relationships: Sequence[Relationship],
    ds: str,
    aliases: dict[str, str],
) -> str:
    """The column other tables point at, else an id-looking unique column,
    else the first column (harmless: pkey is only used for graph node
    identity)."""
    for rel in relationships:
        if rel.parent_table == ds:
            return rel.parent_column
    for c in profile.columns:
        if c.name.lower().endswith("_id") or c.name.lower() == "id":
            return c.name
    return profile.columns[0].name


def build_from_frames(
    spec: DatasetSpec,
    fetch_frame: Callable[[str], pd.DataFrame],
    source_names: dict[str, str],
) -> str:
    """Materialize the engine's training database from workspace frames.

    ``fetch_frame`` reads a workspace dataset (parquet view or federated
    scanner view — the transient LOCAL copy the registry discloses);
    ``source_names`` maps spec table name → workspace dataset id. Returns
    a content fingerprint so callers can key caches on actual data."""
    db_file = db_path(spec.name)  # where the engine's readers look
    db_file.parent.mkdir(parents=True, exist_ok=True)
    db_file.unlink(missing_ok=True)
    digest = hashlib.sha256()
    con = duckdb.connect(str(db_file))
    try:
        for tname, table in spec.tables.items():
            frame = fetch_frame(source_names[tname])
            missing = [c.name for c in table.columns if c.name not in frame.columns]
            if missing:
                raise RelgraphError(
                    f"table '{tname}': workspace columns changed since the "
                    f"spec was derived (missing: {', '.join(missing)})"
                )
            digest.update(tname.encode())
            digest.update(str(len(frame)).encode())
            con.register("df_view", frame)
            select = ", ".join(
                f'CAST("{c.name}" AS {c.duckdb_type}) AS "{c.name}"'
                for c in table.columns
            )
            con.execute(f'CREATE TABLE "{tname}" AS SELECT {select} FROM df_view')
            con.unregister("df_view")
        _check_foreign_keys(con, spec)
    finally:
        con.close()
    return digest.hexdigest()[:16]


def _check_foreign_keys(con: duckdb.DuckDBPyConnection, spec: DatasetSpec) -> None:
    for table in spec.tables.values():
        for fk in table.foreign_keys:
            row = con.execute(
                f'SELECT COUNT(*) FROM "{table.name}" t '
                f'WHERE t."{fk.column}" IS NOT NULL AND NOT EXISTS ('
                f'  SELECT 1 FROM "{fk.ref_table}" r '
                f'  WHERE r."{fk.ref_column}" = t."{fk.column}")'
            ).fetchone()
            if row and row[0]:
                raise RelgraphError(
                    f"referential integrity violation: {row[0]} rows of "
                    f"'{table.name}.{fk.column}' have no matching "
                    f"'{fk.ref_table}.{fk.ref_column}'"
                )


def label_columns(label_sql: str, entity_columns: Sequence[str]) -> list[str]:
    """The entity-table columns the outcome definition references — the
    AUTO-hidden set (AC-6). Tokenized identifier intersection;
    over-exclusion is the safe direction."""
    tokens = {
        t.lower()
        for t in re.findall(r'"([^"]+)"|([A-Za-z_][A-Za-z0-9_]*)', label_sql)
        for t in t
        if t
    }
    return sorted(c for c in entity_columns if c.lower() in tokens)


def time_candidates(tables: dict[str, DatasetProfile]) -> dict[str, list[str]]:
    """Per-table date/datetime columns — the menu the time-column decision
    picks from (AC-2/AC-3)."""
    return {
        ds: [
            c.name
            for c in profile.columns
            if c.inferred_type in (ColumnType.DATE, ColumnType.DATETIME)
        ]
        for ds, profile in tables.items()
    }


# Neighbor-sampling schedule per depth: hops near the entity stay narrow,
# the fan-out lives in the middle (matches the curated berka task, where
# depth 4 is the difference between real signal and a coin flip).
_NEIGHBOR_SCHEDULE = {2: [128, 128], 3: [16, 64, 16], 4: [16, 64, 16, 8]}


def graph_hints(spec: DatasetSpec, entity_table: str) -> dict:
    """Committed depth heuristic: the graph must see one step PAST the
    farthest reachable table (its rows carry the shared-structure signal),
    capped at 4 hops. Deterministic from the validated link set."""
    neighbors: dict[str, set[str]] = {t: set() for t in spec.tables}
    for table in spec.tables.values():
        for fk in table.foreign_keys:
            neighbors[table.name].add(fk.ref_table)
            neighbors[fk.ref_table].add(table.name)
    seen = {entity_table}
    frontier = {entity_table}
    depth = 0
    while frontier:
        frontier = {n for t in frontier for n in neighbors[t]} - seen
        if not frontier:
            break
        seen |= frontier
        depth += 1
    num_layers = max(2, min(4, depth + 1))
    return {
        "num_layers": num_layers,
        "num_neighbors": list(_NEIGHBOR_SCHEDULE[num_layers]),
    }
