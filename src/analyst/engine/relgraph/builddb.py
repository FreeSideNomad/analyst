"""Build the per-dataset DuckDB database from cached tables + metadata.

Reads each cached table CSV with the types declared in the schema, applies the
dataset's transform hook if present, writes db.duckdb, and enforces
referential integrity for every declared foreign key.
"""

from __future__ import annotations

import duckdb
import pandas as pd

from .errors import RelgraphError
from .hooks import load_transform
from .loader import is_cached, table_file
from .registry import cache_root
from .schema import DatasetSpec, TableSpec


def db_path(dataset: str):
    return cache_root() / dataset / "db.duckdb"


def _read_table_raw(spec: DatasetSpec, table: TableSpec) -> pd.DataFrame:
    """Read the cached CSV with every column as text; the dataset's hook (if
    any) then parses dataset-specific encodings, and declared types are cast
    afterwards."""
    path = table_file(spec.name, table.name)
    con = duckdb.connect()
    try:
        return con.execute(
            f"SELECT * FROM read_csv('{path.as_posix()}', "
            f"delim='{table.delimiter}', header=true, all_varchar=true, "
            f"encoding='{table.encoding}')"
        ).df()
    except duckdb.Error as e:
        raise RelgraphError(f"failed to read table '{table.name}' from {path}: {e}")
    finally:
        con.close()


def _check_foreign_keys(con: duckdb.DuckDBPyConnection, spec: DatasetSpec) -> None:
    for table in spec.tables.values():
        for fk in table.foreign_keys:
            orphans = con.execute(
                f'SELECT COUNT(*) FROM "{table.name}" t '
                f'WHERE t."{fk.column}" IS NOT NULL AND NOT EXISTS ('
                f'  SELECT 1 FROM "{fk.ref_table}" r '
                f'  WHERE r."{fk.ref_column}" = t."{fk.column}")'
            ).fetchone()[0]
            if orphans:
                raise RelgraphError(
                    f"referential integrity violation: {orphans} rows of "
                    f"'{table.name}.{fk.column}' have no matching "
                    f"'{fk.ref_table}.{fk.ref_column}'"
                )


def build(spec: DatasetSpec) -> list[str]:
    """Build db.duckdb; return progress messages."""
    if not is_cached(spec):
        missing = [
            t.name
            for t in spec.tables.values()
            if not t.derived and not table_file(spec.name, t.name).is_file()
        ]
        raise RelgraphError(
            f"dataset '{spec.name}' is not cached (missing tables: "
            f"{', '.join(sorted(missing))}); run `relgraph download` first"
        )
    messages: list[str] = []
    path = db_path(spec.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    transform = load_transform(spec.root)
    con = duckdb.connect(str(path))
    try:
        for table in spec.tables.values():
            if table.derived:
                if transform is None:
                    raise RelgraphError(
                        f"table '{table.name}' is derived but the dataset has "
                        f"no hooks.py to materialize it"
                    )
                df = transform(table.name, pd.DataFrame())
                if df is None or df.empty:
                    raise RelgraphError(
                        f"derived table '{table.name}': the hook returned no rows"
                    )
            else:
                df = _read_table_raw(spec, table)
                if transform is not None:
                    out = transform(table.name, df)
                    df = df if out is None else out
            missing = [c.name for c in table.columns if c.name not in df.columns]
            if missing:
                raise RelgraphError(
                    f"table '{table.name}': declared columns missing from the "
                    f"data (after hooks): {', '.join(missing)}"
                )
            con.register("df_view", df)
            if table.columns:
                select = ", ".join(
                    f'CAST("{c.name}" AS {c.duckdb_type}) AS "{c.name}"'
                    for c in table.columns
                )
            else:
                select = "*"
            try:
                con.execute(
                    f'CREATE TABLE "{table.name}" AS SELECT {select} FROM df_view'
                )
            except duckdb.Error as e:
                raise RelgraphError(
                    f"table '{table.name}': cannot cast data to the declared "
                    f"column types: {e}"
                )
            con.unregister("df_view")
            messages.append(f"table {table.name}: {len(df)} rows")
        _check_foreign_keys(con, spec)
    finally:
        con.close()
    messages.append(f"database written to {path}")
    return messages
