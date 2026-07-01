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
from analyst.engine.reader import CsvReader, ReadPlan


def _sql_str(value: str) -> str:
    """Escape a Python string as a DuckDB single-quoted string literal."""
    return "'" + value.replace("'", "''") + "'"


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


class DatasetStore:
    """Owns the analytical store: Parquet files + a DuckDB connection.

    All Parquet/DuckDB access goes through here (CHARTER §2).
    """

    def __init__(self, base_dir: str | os.PathLike[str]):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._con = duckdb.connect(str(self.base_dir / "catalog.duckdb"))
        self._reader = CsvReader()

    def materialize_csv(
        self, dataset: str, csv_path: str | os.PathLike[str]
    ) -> ReadPlan:
        """Read a CSV via the reader, normalize it, and materialize to Parquet.

        The reader resolves encoding, header presence, and final (disambiguated
        or synthesized) column names; we rewrite a clean UTF-8 CSV with those
        names so DuckDB's type inference sees unambiguous input. Returns the
        ReadPlan so the caller can record ingestion facts.

        NOTE: the normalize step reads the whole file in Python; streaming
        transcode is a Slice F (perf/scale) concern.
        """
        plan = self._reader.plan(csv_path)
        text = Path(csv_path).read_bytes().decode(plan.encoding, errors="replace")
        rows = list(csv.reader(io.StringIO(text)))
        data_rows = rows[1:] if plan.has_header else rows

        norm_path = self.base_dir / f"{dataset}.norm.csv"
        with norm_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(plan.column_names)
            writer.writerows(data_rows)

        parquet_path = self.base_dir / f"{dataset}.parquet"
        self._con.execute(
            f"COPY (SELECT * FROM read_csv_auto({_sql_str(str(norm_path))}, header=true)) "
            f"TO {_sql_str(str(parquet_path))} (FORMAT PARQUET)"
        )
        self._con.execute(
            f"CREATE OR REPLACE VIEW {_quote_ident(dataset)} AS "
            f"SELECT * FROM read_parquet({_sql_str(str(parquet_path))})"
        )
        return plan

    def profile(self, dataset: str, sample_cap: int | None = None) -> DatasetProfile:
        if sample_cap is None:
            return profile_relation(self._con, dataset)
        return profile_relation(self._con, dataset, sample_cap=sample_cap)

    def fetch_all(self, dataset: str) -> list[tuple]:
        return self._con.execute(
            f"SELECT * FROM {_quote_ident(dataset)}"
        ).fetchall()
