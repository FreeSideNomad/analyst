"""Generic feature building for the baseline model.

This is the honest, automated version of what hand-built feature pipelines
do: starting from the task's entity table, walk foreign-key paths (up to two
edges, in either direction) to temporal tables, and emit window aggregates
(count, sum, mean, recency) of their numeric columns over standard windows
ending at each row's as-of time. Entity-table attributes come along as-is.

Everything is derived from the dataset's metadata; no dataset-specific code.
"""

from __future__ import annotations

from dataclasses import dataclass

import duckdb
import pandas as pd

from .builddb import db_path
from .errors import RelgraphError
from .schema import DatasetSpec, TableSpec, TaskSpec

WINDOWS_DAYS = (30, 90, 180, 365)
MAX_PATH_EDGES = 2
NUMERIC_TYPES = {"int", "float"}


@dataclass(frozen=True)
class Edge:
    """A traversable fkey edge between two tables (direction-aware)."""

    src: str
    dst: str
    src_column: str
    dst_column: str


@dataclass
class Path:
    edges: tuple[Edge, ...]

    @property
    def terminal(self) -> str:
        return self.edges[-1].dst

    def name(self) -> str:
        return "_".join([self.edges[0].src] + [e.dst for e in self.edges])


def _edges(spec: DatasetSpec) -> list[Edge]:
    out: list[Edge] = []
    for table in spec.tables.values():
        for fk in table.foreign_keys:
            out.append(Edge(table.name, fk.ref_table, fk.column, fk.ref_column))
            out.append(Edge(fk.ref_table, table.name, fk.ref_column, fk.column))
    return out


def temporal_paths(spec: DatasetSpec, entity_table: str) -> list[Path]:
    """All fkey paths (<= MAX_PATH_EDGES) from the entity table that end at a
    temporal table."""
    edges = _edges(spec)
    paths: list[Path] = []
    frontier: list[tuple[Edge, ...]] = [()]
    for _ in range(MAX_PATH_EDGES):
        next_frontier: list[tuple[Edge, ...]] = []
        for prefix in frontier:
            at = prefix[-1].dst if prefix else entity_table
            for edge in edges:
                if edge.src != at:
                    continue
                candidate = prefix + (edge,)
                next_frontier.append(candidate)
                if spec.table(edge.dst).is_temporal:
                    paths.append(Path(candidate))
        frontier = next_frontier
    # Deduplicate identical edge sequences.
    seen: set[tuple] = set()
    unique: list[Path] = []
    for p in paths:
        key = tuple((e.src, e.dst, e.src_column, e.dst_column) for e in p.edges)
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def _numeric_columns(table: TableSpec) -> list[str]:
    return [c.name for c in table.columns if c.type in NUMERIC_TYPES]


def _path_aggregate_sql(
    spec: DatasetSpec, task: TaskSpec, path: Path, window_days: int
) -> tuple[str, list[str]]:
    """SQL producing one row per base row with aggregates over the path's
    terminal temporal table, restricted to [as_of - window, as_of)."""
    terminal = spec.table(path.terminal)
    time_col = terminal.time_column
    prefix = f"{path.name()}_{window_days}d"

    joins = [f'JOIN "{task.entity_table}" e ON e."{task.entity_column}" = b.entity_id']
    prev_alias = "e"
    for i, edge in enumerate(path.edges):
        alias = f"t{i}"
        joins.append(
            f'JOIN "{edge.dst}" {alias} '
            f'ON {alias}."{edge.dst_column}" = {prev_alias}."{edge.src_column}"'
        )
        prev_alias = alias
    term_alias = prev_alias

    aggs = [f'COUNT(*) AS "{prefix}_count"']
    cols = [f"{prefix}_count"]
    excluded = task.excluded_columns(terminal.name)
    for col in _numeric_columns(terminal):
        if col in excluded:
            continue
        for agg in ("sum", "avg"):
            aggs.append(f'{agg}({term_alias}."{col}") AS "{prefix}_{agg}_{col}"')
            cols.append(f"{prefix}_{agg}_{col}")
    aggs.append(
        f"date_diff('day', MAX({term_alias}.\"{time_col}\"), MAX(b.as_of)) "
        f'AS "{prefix}_days_since_last"'
    )
    cols.append(f"{prefix}_days_since_last")

    # Inclusive upper bound: events stamped exactly at the as-of time are
    # known at prediction time (label horizons start strictly after as-of).
    sql = (
        f"SELECT b.rid, {', '.join(aggs)} FROM base b "
        + " ".join(joins)
        + f' WHERE {term_alias}."{time_col}" <= b.as_of'
        f' AND {term_alias}."{time_col}" > b.as_of - INTERVAL {window_days} DAY'
        f" GROUP BY b.rid"
    )
    return sql, cols


def build_features(
    spec: DatasetSpec, task: TaskSpec, frame: pd.DataFrame
) -> pd.DataFrame:
    """Feature matrix aligned with `frame` (entity id + as_of + label + split)."""
    db = db_path(spec.name)
    if not db.is_file():
        raise RelgraphError(
            f"no database for dataset '{spec.name}'; run `relgraph build` first"
        )
    entity = spec.table(task.entity_table)

    base = frame[[task.entity_column, "as_of"]].copy()
    base.columns = ["entity_id", "as_of"]
    base["as_of"] = pd.to_datetime(base["as_of"])
    base["rid"] = range(len(base))

    con = duckdb.connect(str(db), read_only=True)
    try:
        con.register("base", base)
        features = base[["rid"]].copy()

        # Entity table's own attributes (known at as-of time), minus the
        # task's excluded outcome columns.
        excluded = task.excluded_columns(entity.name)
        attr_cols = [
            c
            for c in entity.columns
            if c.name not in (task.entity_column, entity.time_column)
            and c.name not in excluded
            and c.type in ("int", "float", "string", "bool")
        ]
        # Entity timestamp columns (other than the task time column) become
        # "days from as-of" offsets — e.g. a promised delivery date turns
        # into the length of the promised window.
        ts_cols = [
            c
            for c in entity.columns
            if c.type in ("date", "timestamp")
            and c.name not in (task.time_column, entity.time_column)
            and c.name not in excluded
        ]
        selects = [f'e."{c.name}"' for c in attr_cols] + [
            f'date_diff(\'day\', b.as_of, e."{c.name}") AS "entity_days_to_{c.name}"'
            for c in ts_cols
        ]
        if selects:
            attrs = con.execute(
                f"SELECT b.rid, {', '.join(selects)} FROM base b "
                f'JOIN "{entity.name}" e '
                f'ON e."{task.entity_column}" = b.entity_id'
            ).df()
            features = features.merge(attrs, on="rid", how="left")

        for path in temporal_paths(spec, task.entity_table):
            for window in WINDOWS_DAYS:
                sql, cols = _path_aggregate_sql(spec, task, path, window)
                agg = con.execute(sql).df()
                features = features.merge(agg, on="rid", how="left")
                for col in cols:
                    if col.endswith("_count"):
                        features[col] = features[col].fillna(0)
    finally:
        con.close()

    features = features.drop(columns=["rid"])
    for col in features.columns:
        dtype = features[col].dtype
        if not (
            pd.api.types.is_numeric_dtype(dtype)
            or pd.api.types.is_bool_dtype(dtype)
            or isinstance(dtype, pd.CategoricalDtype)
        ):
            features[col] = features[col].astype("category")
    return features
