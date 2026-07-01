"""IngestionService — the application-layer facade the acceptance suite drives.

Dispatches by file format: delimited (CSV/TSV) and JSON produce one dataset;
Excel produces one dataset per non-empty sheet (AC-6). Unsupported formats are
rejected (AC-14); parse failures surface as clean errors (AC-15).
"""

from __future__ import annotations

import dataclasses
import os
import re
from pathlib import Path

from analyst.domain.dataset import DatasetSummary, IngestionResult
from analyst.engine.excel import ExcelReader
from analyst.engine.reader import UnsupportedFormatError
from analyst.engine.store import DatasetStore

_DELIMITED = {".csv": ",", ".tsv": "\t"}
_EXCEL = {".xlsx", ".xls"}
_SUPPORTED = "CSV, TSV, Excel, JSON"


def _sanitize(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
    return slug or "dataset"


class IngestionService:
    """Orchestrates ingestion. Thin — no bulk data handling of its own."""

    def __init__(self, store: DatasetStore):
        self.store = store

    def ingest(self, source: str | os.PathLike[str]) -> IngestionResult:
        path = Path(source)
        ext = path.suffix.lower()

        if ext in _DELIMITED:
            summary = self._ingest_delimited(
                _sanitize(path.stem), path, _DELIMITED[ext]
            )
            return IngestionResult((summary,))
        if ext == ".json":
            return IngestionResult((self._ingest_json(_sanitize(path.stem), path),))
        if ext in _EXCEL:
            return self._ingest_excel(path)
        raise UnsupportedFormatError(
            f"Unsupported file format '{ext or '(none)'}'. "
            f"Supported formats: {_SUPPORTED}."
        )

    def _ingest_delimited(
        self, dataset: str, path: str | os.PathLike[str], delimiter: str
    ) -> DatasetSummary:
        plan = self.store.materialize_delimited(dataset, path, delimiter)
        profile = dataclasses.replace(
            self.store.profile(dataset),
            encoding=plan.encoding,
            synthesized_headers=plan.synthesized_headers,
            had_duplicate_columns=plan.had_duplicate_columns,
        )
        return DatasetSummary(dataset, profile)

    def _ingest_json(
        self, dataset: str, path: str | os.PathLike[str]
    ) -> DatasetSummary:
        nested = self.store.materialize_json(dataset, path)
        profile = self.store.profile(dataset)
        if nested:
            columns = tuple(
                dataclasses.replace(c, is_nested=True) if c.name in nested else c
                for c in profile.columns
            )
            profile = dataclasses.replace(profile, columns=columns)
        return DatasetSummary(dataset, profile)

    def _ingest_excel(self, path: Path) -> IngestionResult:
        summaries = [
            self._ingest_delimited(_sanitize(sheet_name), csv_path, ",")
            for sheet_name, csv_path in ExcelReader().sheets(path, self.store.base_dir)
        ]
        return IngestionResult(tuple(summaries))
