"""DatasetStore — materializes data to Parquet and keeps it queryable via DuckDB.

Slice A: CSV → Parquet → registered view. Bulk data stays local (governance).
"""

from __future__ import annotations

import csv
import io
import os
from pathlib import Path

import duckdb

from analyst.domain.profile import DatasetProfile
from analyst.engine.profiler import profile_relation
from analyst.engine.reader import CsvReader, MalformedFileError, ReadPlan


def _sql_str(value: str) -> str:
    """Escape a Python string as a DuckDB single-quoted string literal."""
    return "'" + value.replace("'", "''") + "'"


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


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
        self._con = duckdb.connect(str(self.base_dir / "catalog.duckdb"))
        self._reader = CsvReader()

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

    def datasets(self) -> list[str]:
        """Persisted dataset (view) names — the source of truth across restarts
        (HIGH H2). Excludes transient/internal relations."""
        rows = self._con.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'main' ORDER BY table_name"
        ).fetchall()
        return [str(r[0]) for r in rows if not str(r[0]).startswith(("fed_", "__"))]

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

    def schema(self, dataset: str) -> tuple[tuple[str, str], ...]:
        """The established schema: (column name, inferred type) pairs."""
        return tuple(
            (col.name, col.inferred_type.value) for col in self.profile(dataset).columns
        )

    def profile(self, dataset: str, sample_cap: int | None = None) -> DatasetProfile:
        if sample_cap is None:
            return profile_relation(self._con, dataset)
        return profile_relation(self._con, dataset, sample_cap=sample_cap)

    def fetch_all(self, dataset: str) -> list[tuple]:
        return self._con.execute(f"SELECT * FROM {_quote_ident(dataset)}").fetchall()

    def delete(self, dataset: str) -> None:
        """Drop the dataset's view and remove all its versions (AC-20)."""
        self._con.execute(f"DROP VIEW IF EXISTS {_quote_ident(dataset)}")
        (self.base_dir / f"{dataset}.norm.csv").unlink(missing_ok=True)
        for path in self.base_dir.glob(f"{dataset}.v*.parquet"):
            path.unlink(missing_ok=True)

    def exists(self, dataset: str) -> bool:
        rows = self._con.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_name = ?",
            [dataset],
        ).fetchall()
        return len(rows) > 0
