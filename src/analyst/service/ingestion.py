"""IngestionService — the application-layer facade the acceptance suite drives.

Dispatches by file format: delimited (CSV/TSV) and JSON produce one dataset;
Excel produces one dataset per non-empty sheet (AC-6). Unsupported formats are
rejected (AC-14); parse failures surface as clean errors (AC-15).
"""

from __future__ import annotations

import dataclasses
import os
import re
from collections.abc import Callable
from pathlib import Path

from analyst.agentic.cataloguer import Cataloguer
from analyst.domain.catalog import CatalogEntry, Clarification, payload_from_profile
from analyst.domain.dataset import DatasetSummary, IngestionResult, RefreshResult
from analyst.domain.profile import DatasetProfile
from analyst.domain.status import IngestionStatus
from analyst.engine.excel import ExcelReader
from analyst.engine.reader import FileTooLargeError, UnsupportedFormatError
from analyst.engine.store import DatasetStore

_DELIMITED = {".csv": ",", ".tsv": "\t"}
_EXCEL = {".xlsx", ".xls"}
_SUPPORTED = "CSV, TSV, Excel, JSON"
DEFAULT_MAX_BYTES = 1_000_000_000  # ~1 GB envelope (AC-21)

StatusSink = Callable[[str, IngestionStatus], None]


def _sanitize(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
    return slug or "dataset"


class IngestionService:
    """Orchestrates ingestion. Thin — no bulk data handling of its own.

    A cataloguer is optional: when present, each dataset gets an agent-authored
    catalog entry (AC-4). If cataloguing fails, the dataset is rolled back so no
    partial dataset remains (AC-17).
    """

    def __init__(
        self,
        store: DatasetStore,
        cataloguer: Cataloguer | None = None,
        max_bytes: int = DEFAULT_MAX_BYTES,
        status_sink: StatusSink | None = None,
    ):
        self.store = store
        self.cataloguer = cataloguer
        self.max_bytes = max_bytes
        self.status_sink = status_sink

    def _report(self, dataset: str, status: IngestionStatus) -> None:
        if self.status_sink is not None:
            self.status_sink(dataset, status)

    def delete(self, dataset: str) -> None:
        """Remove a dataset's data and (a later feature) its catalog entry (AC-20)."""
        self.store.delete(dataset)

    def refresh(
        self,
        dataset: str,
        source: str | os.PathLike[str],
        loosen: bool = False,
    ) -> RefreshResult:
        """Reload new data into an existing dataset's schema (AC-18, AC-19).

        The new data is validated against the established schema BEFORE the
        existing data is touched. Conforming data (or loosen=True) is installed
        as a new, non-destructive version; non-conforming data leaves the
        existing data untouched and returns a clarification asking to loosen.
        """
        src = Path(source)
        if src.suffix.lower() not in _DELIMITED:
            raise UnsupportedFormatError(
                f"Refresh currently supports delimited files; got '{src.suffix}'."
            )
        delimiter = _DELIMITED[src.suffix.lower()]
        established = self.store.schema(dataset)

        candidate = f"{dataset}__candidate"
        self.store.materialize_delimited(candidate, src, delimiter)
        candidate_schema = self.store.schema(candidate)
        self.store.delete(candidate)

        if candidate_schema == established or loosen:
            self.store.materialize_delimited(dataset, src, delimiter)
            return RefreshResult(
                dataset_name=dataset,
                replaced=True,
                version=len(self.store.versions(dataset)),
                profile=self.store.profile(dataset),
            )
        return RefreshResult(
            dataset_name=dataset,
            replaced=False,
            clarification=Clarification(
                question=(
                    f"The new data does not conform to the established schema of "
                    f"'{dataset}'. Loosen the validations and replace anyway?"
                ),
                options=("Loosen validations and replace", "Keep the existing data"),
            ),
        )

    def _catalog(self, dataset: str, profile: DatasetProfile) -> CatalogEntry | None:
        if self.cataloguer is None:
            return None
        from analyst.agentic.cataloguer import CatalogingError

        try:
            return self.cataloguer.catalog(payload_from_profile(dataset, profile))
        except CatalogingError:
            self.store.delete(dataset)  # rollback — no partial dataset (AC-17)
            raise

    def ingest(self, source: str | os.PathLike[str]) -> IngestionResult:
        path = Path(source)
        name = _sanitize(path.stem)
        self._report(name, IngestionStatus.IN_PROGRESS)
        try:
            self._check_size(path)
            result = self._dispatch(path)
        except Exception:
            self._report(name, IngestionStatus.FAILED)
            raise
        self._report(name, IngestionStatus.COMPLETE)
        return result

    def _check_size(self, path: Path) -> None:
        size = path.stat().st_size if path.exists() else 0
        if size > self.max_bytes:
            raise FileTooLargeError(
                f"The file is {size} bytes — too large for this version "
                f"(limit {self.max_bytes} bytes)."
            )

    def _dispatch(self, path: Path) -> IngestionResult:
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
        return DatasetSummary(dataset, profile, self._catalog(dataset, profile))

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
        return DatasetSummary(dataset, profile, self._catalog(dataset, profile))

    def _ingest_excel(self, path: Path) -> IngestionResult:
        summaries = [
            self._ingest_delimited(_sanitize(sheet_name), csv_path, ",")
            for sheet_name, csv_path in ExcelReader().sheets(path, self.store.base_dir)
        ]
        return IngestionResult(tuple(summaries))
