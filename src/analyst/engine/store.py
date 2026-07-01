"""DatasetStore — materializes data to Parquet and keeps it queryable via DuckDB.

Slice A: CSV → Parquet → registered view. Bulk data stays local (governance).
"""
from __future__ import annotations

import os
from pathlib import Path

import duckdb

from analyst.domain.profile import DatasetProfile
from analyst.engine.profiler import profile_relation


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

    def materialize_csv(self, dataset: str, csv_path: str | os.PathLike[str]) -> None:
        """Read a CSV, write it to Parquet, and register it as a queryable view."""
        parquet_path = self.base_dir / f"{dataset}.parquet"
        self._con.execute(
            f"COPY (SELECT * FROM read_csv_auto({_sql_str(str(csv_path))}, header=true)) "
            f"TO {_sql_str(str(parquet_path))} (FORMAT PARQUET)"
        )
        self._con.execute(
            f"CREATE OR REPLACE VIEW {_quote_ident(dataset)} AS "
            f"SELECT * FROM read_parquet({_sql_str(str(parquet_path))})"
        )

    def profile(self, dataset: str, sample_cap: int | None = None) -> DatasetProfile:
        if sample_cap is None:
            return profile_relation(self._con, dataset)
        return profile_relation(self._con, dataset, sample_cap=sample_cap)

    def fetch_all(self, dataset: str) -> list[tuple]:
        return self._con.execute(
            f"SELECT * FROM {_quote_ident(dataset)}"
        ).fetchall()
