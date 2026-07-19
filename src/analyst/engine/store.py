"""DatasetStore — materializes data to Parquet and keeps it queryable via DuckDB.

Slice A: CSV → Parquet → registered view. Bulk data stays local (governance).
"""

from __future__ import annotations

import csv
import io
import os
import re
import threading
from collections.abc import Callable, Sequence
from functools import wraps
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar, cast

if TYPE_CHECKING:
    from analyst.domain.relationships import Relationship
    from analyst.engine.relationships import DiscoverTable

import duckdb

from analyst.domain.profile import DatasetProfile
from analyst.domain.relationships import Relationship
from analyst.engine.profiler import profile_relation
from analyst.engine.reader import CsvReader, MalformedFileError, ReadPlan
from analyst.engine.relationships import DiscoverTable, discover

_F = TypeVar("_F", bound=Callable[..., Any])


def _synchronized(method: _F) -> _F:
    """Serialize a store method on the store's lock (SECURITY M4).

    FastAPI runs sync endpoints in a threadpool; a DuckDB connection is not safe
    for concurrent use, so every operation on the shared connection takes the
    (reentrant) store lock.
    """

    @wraps(method)
    def wrapper(self: "DatasetStore", *args: Any, **kwargs: Any) -> Any:
        with self._lock:
            return method(self, *args, **kwargs)

    return cast(_F, wrapper)


def _sql_str(value: str) -> str:
    """Escape a Python string as a DuckDB single-quoted string literal."""
    return "'" + value.replace("'", "''") + "'"


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def query_alias_base(real: str) -> str:
    """The readable (lossy) base SQL alias for a dataset id — dataset ids carry
    dots (``orders.csv``) an LLM misreads as ``schema.table``. Lossy, so the
    store's registry disambiguates real collisions on top of this."""
    return "q_" + re.sub(r"\W", "_", real)


def _is_nested_type(duckdb_type: str) -> bool:
    """True for DuckDB composite types (objects/arrays/maps) and JSON."""
    upper = duckdb_type.upper()
    return (
        upper.startswith("STRUCT")
        or upper.startswith("MAP")
        or upper == "JSON"
        or upper.endswith("[]")
    )


class DatasetStore:
    """Owns the analytical store: Parquet files + a DuckDB connection.

    All Parquet/DuckDB access goes through here (CHARTER §2).
    """

    def __init__(self, base_dir: str | os.PathLike[str]):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()  # M4: serialize the DuckDB connection
        self._con = duckdb.connect(str(self.base_dir / "catalog.duckdb"))
        # Review #5: a federated GROUP BY/JOIN is NOT pushed down — DuckDB streams
        # the projected rows into this box. Cap memory so a runaway query over a
        # huge remote source fails CLEANLY (caught -> abstain) instead of OOM-ing
        # the box. Operator-tunable; unset -> DuckDB's default (80% RAM).
        mem = os.environ.get("ANALYST_MAX_MEMORY")
        if mem:
            try:
                self._con.execute(f"SET memory_limit = '{mem}'")
            except duckdb.Error:
                pass
        self._reader = CsvReader()
        # Feature 007: names of views backing connected-database tables. They are
        # queryable (planner SQL runs against them) but are NOT local datasets.
        self._fed_views: set[str] = set()
        # 007-fix: injective dataset-id <-> SQL-alias registry (review #1). The
        # readable base is lossy, so real collisions get a numeric suffix.
        self._alias_by_real: dict[str, str] = {}
        self._real_by_alias: dict[str, str] = {}

    @_synchronized
    def materialize_delimited(
        self,
        dataset: str,
        source_path: str | os.PathLike[str],
        delimiter: str = ",",
    ) -> ReadPlan:
        """Read a delimited file (CSV/TSV) via the reader, normalize it, and
        materialize to Parquet.

        The reader resolves encoding, header presence, and final (disambiguated
        or synthesized) column names; we rewrite a clean UTF-8 CSV with those
        names so DuckDB's type inference sees unambiguous input. Returns the
        ReadPlan so the caller can record ingestion facts.

        NOTE: the normalize step reads the whole file in Python; streaming
        transcode is a Slice F (perf/scale) concern.
        """
        plan = self._reader.plan(source_path, delimiter=delimiter)
        text = Path(source_path).read_bytes().decode(plan.encoding, errors="replace")
        rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
        data_rows = rows[1:] if plan.has_header else rows

        norm_path = self.base_dir / f"{dataset}.norm.csv"
        with norm_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(plan.column_names)
            writer.writerows(data_rows)

        self._register_parquet(
            dataset,
            f"SELECT * FROM read_csv_auto({_sql_str(str(norm_path))}, header=true)",
        )
        return plan

    @_synchronized
    def materialize_json(
        self, dataset: str, json_path: str | os.PathLike[str]
    ) -> tuple[str, ...]:
        """Materialize a JSON file (array of records) to Parquet.

        Nested values (objects/arrays) are preserved as JSON text rather than
        dropped; their column names are returned so the caller can record them.
        """
        src = _sql_str(str(json_path))
        try:
            schema = self._con.execute(
                f"DESCRIBE SELECT * FROM read_json_auto({src})"
            ).fetchall()
            nested = tuple(row[0] for row in schema if _is_nested_type(row[1]))
            select = ", ".join(
                (
                    f"to_json({_quote_ident(name)}) AS {_quote_ident(name)}"
                    if _is_nested_type(dtype)
                    else _quote_ident(name)
                )
                for name, dtype, *_ in schema
            )
            self._register_parquet(
                dataset, f"SELECT {select} FROM read_json_auto({src})"
            )
        except duckdb.Error as exc:
            # HIGH H4: a parse failure must surface as a clean 4xx, not a 500.
            raise MalformedFileError(f"The JSON file could not be read: {exc}") from exc
        return nested

    @_synchronized
    def datasets(self) -> list[str]:
        """Persisted dataset (view) names — the source of truth across restarts
        (HIGH H2). Excludes transient/internal relations."""
        # Scope to the PRIMARY database's catalog — an ATTACHed cross-source DB
        # (feature 009) also exposes its tables under table_schema='main' but a
        # different table_catalog, and those must not be treated as datasets.
        rows = self._con.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'main' AND table_catalog = current_database() "
            "ORDER BY table_name"
        ).fetchall()
        return [
            str(r[0])
            for r in rows
            if not str(r[0]).startswith(("fed_", "__"))
            and str(r[0]) not in self._fed_views
        ]

    @_synchronized
    def register_query_alias(self, real: str) -> str:
        """Register (idempotently) a dot-free TEMP view over dataset ``real`` and
        return its INJECTIVE alias. TEMP so it never persists nor leaks into
        datasets(); the planner/validator/execution reference the alias. The
        readable base is lossy (review #1), so a real collision — two distinct
        ids like ``sales.q1.csv`` and ``sales_q1.csv`` — gets a numeric suffix
        instead of silently overwriting."""
        alias = self._alias_by_real.get(real)
        if alias is None:
            base = query_alias_base(real)
            alias = base
            suffix = 2
            while alias in self._real_by_alias:  # collision with a DIFFERENT id
                alias = f"{base}_{suffix}"
                suffix += 1
            self._alias_by_real[real] = alias
            self._real_by_alias[alias] = real
        self._con.execute(
            f"CREATE OR REPLACE TEMP VIEW {_quote_ident(alias)} AS "
            f"SELECT * FROM {_quote_ident(real)}"
        )
        return alias

    def alias_for(self, real: str) -> str:
        """The registered alias for a dataset (registering it if needed)."""
        return self.register_query_alias(real)

    @_synchronized
    def validation_problems(self, sql: str) -> list[str]:
        """Pre-execution validation via DuckDB's REAL parser/binder (review #2),
        replacing a regex pseudo-parser that false-rejected valid SQL
        (``EXTRACT(YEAR FROM d)``, ``COUNT(*) c``). The AST safety guard (single
        SELECT, no table functions, real base tables) PLUS a bind check
        (closed-world: only known tables/columns resolve) — the query is bound,
        never executed. Returns problem strings; empty means valid."""
        from analyst.engine.sql_guard import UnsafeQueryError, assert_safe_select

        try:
            assert_safe_select(self._con, sql)
        except UnsafeQueryError as exc:
            return [str(exc)]
        try:
            self._con.execute("PREPARE __analyst_validate AS " + sql)
            self._con.execute("DEALLOCATE __analyst_validate")
        except duckdb.Error as exc:
            return [str(exc).splitlines()[0]]
        return []

    def dataset_for_alias(self, alias: str) -> str | None:
        """The dataset id an alias maps back to (for the friendly trust trail)."""
        return self._real_by_alias.get(alias)

    def query_alias_map(self) -> dict[str, str]:
        """A copy of the alias -> dataset-id map (for the friendly trust trail)."""
        return dict(self._real_by_alias)

    @_synchronized
    def attach_database(
        self, connection: str, spec: object, tables: tuple[str, ...]
    ) -> None:
        """Feature 007: ATTACH a connected database (scanner engine) into this
        connection and register each table as a TEMP view named
        ``<connection>.<table>`` — the dataset id the planner uses — so planner
        SQL executes against it with scanner push-down. Read-only; bulk data
        stays at the source. TEMP so the attach (which is not persisted, and
        whose secret is never written to disk) leaves nothing dangling on
        restart — the user re-connects."""
        from analyst.engine.federation import build_attach_sql, source_schema

        alias = f"__fed_{connection}"
        for ext in ("sqlite", "postgres"):
            try:
                self._con.execute(f"INSTALL {ext}; LOAD {ext};")
            except duckdb.Error:
                pass  # already present, or offline — ATTACH surfaces a clean error
        # Idempotent: a reconnect (credential restore, retry after an outage)
        # must not collide with a previous attach (defect 2026-07-18).
        try:
            self._con.execute(f"DETACH DATABASE IF EXISTS {_quote_ident(alias)}")
        except duckdb.Error:
            pass
        self._con.execute(build_attach_sql(spec, alias))  # type: ignore[arg-type]
        schema = source_schema(spec.engine)  # type: ignore[attr-defined]
        for table in tables:
            view = f"{connection}.{table}"
            self._con.execute(
                f"CREATE OR REPLACE TEMP VIEW {_quote_ident(view)} AS SELECT * FROM "
                f"{_quote_ident(alias)}.{_quote_ident(schema)}.{_quote_ident(table)}"
            )
            self._fed_views.add(view)

    @_synchronized
    def detach_database(self, connection: str) -> None:
        """Drop a connected database's views and DETACH it."""
        alias = f"__fed_{connection}"
        for view in [v for v in self._fed_views if v.startswith(f"{connection}.")]:
            self._con.execute(f"DROP VIEW IF EXISTS {_quote_ident(view)}")
            self._fed_views.discard(view)
        try:
            self._con.execute(f"DETACH {_quote_ident(alias)}")
        except duckdb.Error:
            pass

    @_synchronized
    def _register_parquet(self, dataset: str, select_sql: str) -> None:
        """Write the next version's Parquet and point the dataset view at it.

        Each materialization is a new, retained version (AC-19); the view always
        resolves to the latest.
        """
        # M8: derive from the max existing version, not the count — a gap in
        # versions (e.g. [1, 3]) must never make a new write overwrite v3.
        version = max(self.versions(dataset), default=0) + 1
        parquet_path = self.base_dir / f"{dataset}.v{version}.parquet"
        self._con.execute(
            f"COPY ({select_sql}) TO {_sql_str(str(parquet_path))} (FORMAT PARQUET)"
        )
        self._con.execute(
            f"CREATE OR REPLACE VIEW {_quote_ident(dataset)} AS "
            f"SELECT * FROM read_parquet({_sql_str(str(parquet_path))})"
        )

    def versions(self, dataset: str) -> list[int]:
        """Sorted version numbers retained on disk for a dataset."""
        prefix = f"{dataset}.v"
        out: list[int] = []
        for path in self.base_dir.glob(f"{dataset}.v*.parquet"):
            num = path.name[len(prefix) : -len(".parquet")]
            if num.isdigit():
                out.append(int(num))
        return sorted(out)

    @_synchronized
    def schema(self, dataset: str) -> tuple[tuple[str, str], ...]:
        """The established schema: (column name, inferred type) pairs."""
        return tuple(
            (col.name, col.inferred_type.value) for col in self.profile(dataset).columns
        )

    @_synchronized
    def profile(self, dataset: str, sample_cap: int | None = None) -> DatasetProfile:
        if sample_cap is None:
            return profile_relation(self._con, dataset)
        return profile_relation(self._con, dataset, sample_cap=sample_cap)

    @_synchronized
    def fetch_all(self, dataset: str) -> list[tuple]:
        return self._con.execute(f"SELECT * FROM {_quote_ident(dataset)}").fetchall()

    @_synchronized
    def create_projection(
        self, view: str, dataset: str, columns: tuple[str, ...]
    ) -> None:
        """A queryable view of selected columns (feature 012: the accepted
        feature table, with lineage to its source dataset)."""
        cols = ", ".join(_quote_ident(c) for c in columns)
        self._con.execute(
            f"CREATE OR REPLACE VIEW {_quote_ident(view)} AS "
            f"SELECT {cols} FROM {_quote_ident(dataset)}"
        )

    @_synchronized
    def drop_projection(self, view: str) -> None:
        self._con.execute(f"DROP VIEW IF EXISTS {_quote_ident(view)}")

    @_synchronized
    def fetch_frame(self, dataset: str, columns: tuple[str, ...] = ()):  # noqa: ANN201
        """The dataset (or selected columns) as a pandas DataFrame — the
        committed trainer's read path (feature 012). Engine-internal."""
        cols = ", ".join(_quote_ident(c) for c in columns) if columns else "*"
        return self._con.execute(f"SELECT {cols} FROM {_quote_ident(dataset)}").df()

    @_synchronized
    def value_counts(self, dataset: str, column: str) -> dict[str, int]:
        """Non-null value → row count for one column (feature 013 detection)."""
        rows = self._con.execute(
            f"SELECT {_quote_ident(column)}, COUNT(*) FROM {_quote_ident(dataset)} "
            f"WHERE {_quote_ident(column)} IS NOT NULL GROUP BY 1"
        ).fetchall()
        return {str(value): int(count) for value, count in rows}

    @_synchronized
    def apply_normalization(
        self, dataset: str, mappings: dict[str, dict[str, str]]
    ) -> None:
        """Point the dataset view at the latest Parquet with explicit value
        mappings folded in (feature 013). The Parquet is never touched —
        approve/revoke only ever rewrite this view. Empty mappings restore
        the plain view."""
        version = max(self.versions(dataset), default=0)
        if version == 0:
            raise KeyError(dataset)
        path = _sql_str(str(self.base_dir / f"{dataset}.v{version}.parquet"))
        columns = [
            row[0]
            for row in self._con.execute(
                f"DESCRIBE SELECT * FROM read_parquet({path})"
            ).fetchall()
        ]
        parts = []
        for column in columns:
            mapping = mappings.get(column)
            if mapping:
                whens = " ".join(
                    f"WHEN {_sql_str(raw)} THEN {_sql_str(canonical)}"
                    for raw, canonical in sorted(mapping.items())
                )
                parts.append(
                    f"CASE {_quote_ident(column)} {whens} "
                    f"ELSE {_quote_ident(column)} END AS {_quote_ident(column)}"
                )
            else:
                parts.append(_quote_ident(column))
        self._con.execute(
            f"CREATE OR REPLACE VIEW {_quote_ident(dataset)} AS "
            f"SELECT {', '.join(parts)} FROM read_parquet({path})"
        )

    @_synchronized
    def delete(self, dataset: str) -> None:
        """Drop the dataset's view and remove all its versions (AC-20)."""
        self._con.execute(f"DROP VIEW IF EXISTS {_quote_ident(dataset)}")
        (self.base_dir / f"{dataset}.norm.csv").unlink(missing_ok=True)
        for path in self.base_dir.glob(f"{dataset}.v*.parquet"):
            path.unlink(missing_ok=True)

    @_synchronized
    def discover_relationships(
        self,
        extra: Sequence[DiscoverTable] | None = None,
        include_federated: bool = False,
    ) -> list[Relationship]:
        """Discover relationships across all datasets (parquet views) in this
        store's connection — plus any ``extra`` DiscoverTable relations already
        registered in it (e.g. an attached DB, for cross-source). Local only.

        ``include_federated`` (feature 010) also scans the connection-backed
        ``<connection>.<table>`` views ATTACHed for query, so file↔DB
        relationships are discovered under record-matching names. Profiling
        those views reads through the scanner (remote for Postgres) — hot-path
        callers should run it in the background.
        """
        from analyst.engine.relationships import DiscoverTable

        tables = [
            DiscoverTable(name=name, profile=profile_relation(self._con, name))
            for name in self.datasets()
        ]
        if include_federated:
            tables += [
                DiscoverTable(
                    name=view,
                    profile=profile_relation(self._con, view),
                    relation=_quote_ident(view),
                )
                for view in sorted(self._fed_views)
            ]
        if extra:
            tables += list(extra)
        return discover(self._con, tables)

    @_synchronized
    def attach_sqlite(self, alias: str, path: str, tables: tuple[str, ...]) -> object:
        """Attach a SQLite database into this connection and register each table
        as a scanner-backed temp view, so file↔DB discovery runs in one
        connection (AC-6). Returns the DiscoverTable relations to include."""
        from analyst.engine.relationships import DiscoverTable

        self._con.execute(
            f"ATTACH {_sql_str(path)} AS {_quote_ident(alias)} (TYPE sqlite, READ_ONLY)"
        )
        out = []
        for table in tables:
            view = f"__fed_{alias}_{table}"
            self._con.execute(
                f"CREATE OR REPLACE TEMP VIEW {_quote_ident(view)} AS SELECT * FROM "
                f"{_quote_ident(alias)}.main.{_quote_ident(table)}"
            )
            out.append(
                DiscoverTable(
                    name=table,
                    profile=profile_relation(self._con, view),
                    relation=_quote_ident(view),
                )
            )
        return out

    @_synchronized
    def exists(self, dataset: str) -> bool:
        rows = self._con.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_name = ?",
            [dataset],
        ).fetchall()
        return len(rows) > 0
