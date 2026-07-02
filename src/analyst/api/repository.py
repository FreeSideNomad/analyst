"""DatasetRepository — the seam between the API and where data lives.

StoreRepository    → the real IngestionService + DatasetStore (DuckDB/Parquet),
                     the DEFAULT.
FixtureRepository  → in-memory domain objects (opt-in mock: ANALYST_FIXTURES=1).

Both return the same domain `DatasetSummary`; the API layer serializes it. The
repository owns only the *envelope* metadata the domain doesn't carry
(file name, status, ingested-at).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol

from analyst.api import fixtures
from analyst.domain.dataset import DatasetSummary, RefreshResult
from analyst.domain.status import IngestionStatus


@dataclass
class DatasetRecord:
    """A dataset plus the API-envelope metadata the domain doesn't track."""

    summary: DatasetSummary
    file_name: str
    status: IngestionStatus = IngestionStatus.COMPLETE
    ingested_at: str | None = None
    started_at: float | None = None  # monotonic; drives simulated progress

    @property
    def name(self) -> str:
        return self.summary.name


class DatasetRepository(Protocol):
    def list_datasets(self) -> list[DatasetRecord]: ...
    def get_dataset(self, name: str) -> DatasetRecord | None: ...
    def catalog(self) -> dict[str, object]: ...
    def delete(self, name: str) -> None: ...
    def ingest(self, file_name: str, content: bytes) -> list[DatasetRecord]: ...
    def status(self, name: str) -> tuple[IngestionStatus, str | None, int | None]: ...
    def refresh(self, name: str, file_name: str, content: bytes) -> RefreshResult: ...


# --------------------------------------------------------------------------- #
# Fixtures — the mock, in Python.
# --------------------------------------------------------------------------- #
_PHASES = ["materializing", "profiling", "cataloguing"]
_SIM_SECONDS = 3.0  # how long a simulated ingest "runs"


class FixtureRepository:
    """In-memory workspace seeded from `api.fixtures`. Ingest is simulated."""

    def __init__(self) -> None:
        self._records: dict[str, DatasetRecord] = {}
        for i, summary in enumerate(fixtures.seed()):
            self._records[summary.name] = DatasetRecord(
                summary=summary,
                file_name=f"{summary.name}.csv",
                status=IngestionStatus.COMPLETE,
                ingested_at=f"2025-12-1{i}",
            )

    def list_datasets(self) -> list[DatasetRecord]:
        return list(self._records.values())

    def get_dataset(self, name: str) -> DatasetRecord | None:
        return self._records.get(name)

    def catalog(self) -> dict[str, object]:
        return {
            r.name: r.summary.catalog
            for r in self._records.values()
            if r.summary.catalog
        }

    def delete(self, name: str) -> None:
        self._records.pop(name, None)

    def ingest(self, file_name: str, content: bytes) -> list[DatasetRecord]:
        summary = fixtures.uploaded_transactions()
        record = DatasetRecord(
            summary=summary,
            file_name=file_name or f"{summary.name}.csv",
            status=IngestionStatus.IN_PROGRESS,
            ingested_at="2026-07-01",
            started_at=time.monotonic(),
        )
        self._records[summary.name] = record
        return [record]

    def status(self, name: str) -> tuple[IngestionStatus, str | None, int | None]:
        record = self._records.get(name)
        if record is None:
            return IngestionStatus.FAILED, None, None
        if (
            record.status is not IngestionStatus.IN_PROGRESS
            or record.started_at is None
        ):
            return record.status, None, 100
        elapsed = time.monotonic() - record.started_at
        if elapsed >= _SIM_SECONDS:
            record.status = IngestionStatus.COMPLETE
            record.started_at = None
            return IngestionStatus.COMPLETE, None, 100
        frac = elapsed / _SIM_SECONDS
        phase = _PHASES[min(len(_PHASES) - 1, int(frac * len(_PHASES)))]
        return IngestionStatus.IN_PROGRESS, phase, int(frac * 100)

    def refresh(self, name: str, file_name: str, content: bytes) -> RefreshResult:
        """Simulated refresh: conforming data, new non-destructive version."""
        record = self._records.get(name)
        if record is None:
            raise KeyError(name)
        return RefreshResult(
            dataset_name=name,
            replaced=True,
            version=2,
            profile=record.summary.profile,
        )


# --------------------------------------------------------------------------- #
# Real store — wraps the implemented feature-001 service.
# --------------------------------------------------------------------------- #
class StoreRepository:
    """Adapts the real IngestionService/DatasetStore to the repository port.

    Only feature-001 file ingestion is wired; catalogs come from the summaries
    the service returns. Requires ANALYST_DATA_DIR.
    """

    def __init__(self, data_dir: str) -> None:
        import tempfile

        from analyst.engine.store import DatasetStore
        from analyst.service.ingestion import IngestionService

        self._tempfile = tempfile
        self.store = DatasetStore(data_dir)
        self.service = IngestionService(self.store)
        self._records: dict[str, DatasetRecord] = {}

    def list_datasets(self) -> list[DatasetRecord]:
        return list(self._records.values())

    def get_dataset(self, name: str) -> DatasetRecord | None:
        return self._records.get(name)

    def catalog(self) -> dict[str, object]:
        return {
            r.name: r.summary.catalog
            for r in self._records.values()
            if r.summary.catalog
        }

    def delete(self, name: str) -> None:
        self.service.delete(name)
        self._records.pop(name, None)

    def ingest(self, file_name: str, content: bytes) -> list[DatasetRecord]:
        # Write under the REAL file name (in a temp dir) — the service derives
        # the dataset name from the file's stem, so a NamedTemporaryFile would
        # produce garbage dataset names like "tmps9jbs9y1".
        with self._tempfile.TemporaryDirectory() as tmp_dir:
            from pathlib import Path

            tmp_path = Path(tmp_dir) / (file_name or "upload.csv")
            tmp_path.write_bytes(content)
            result = self.service.ingest(tmp_path)
        out: list[DatasetRecord] = []
        for summary in result.datasets:
            rec = DatasetRecord(
                summary=summary,
                file_name=file_name,
                status=IngestionStatus.COMPLETE,
                ingested_at=time.strftime("%Y-%m-%d"),
            )
            self._records[summary.name] = rec
            out.append(rec)
        return out

    def status(self, name: str) -> tuple[IngestionStatus, str | None, int | None]:
        record = self._records.get(name)
        if record is None:
            return IngestionStatus.FAILED, None, None
        return record.status, None, 100

    def refresh(self, name: str, file_name: str, content: bytes) -> RefreshResult:
        """Real refresh: schema-validated, versioned (feature-001 semantics)."""
        record = self._records.get(name)
        if record is None:
            raise KeyError(name)
        suffix = "." + file_name.rsplit(".", 1)[-1] if "." in file_name else ".csv"
        with self._tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        result = self.service.refresh(name, tmp_path)
        if result.replaced and result.profile is not None:
            import dataclasses

            record.summary = dataclasses.replace(record.summary, profile=result.profile)
        return result
