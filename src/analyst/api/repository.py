"""DatasetRepository — the seam between the API and where data lives.

StoreRepository    → the real IngestionService + DatasetStore (DuckDB/Parquet),
                     the DEFAULT.
FixtureRepository  → in-memory domain objects (opt-in mock: ANALYST_FIXTURES=1).

Both return the same domain `DatasetSummary`; the API layer serializes it. The
repository owns only the *envelope* metadata the domain doesn't carry
(file name, status, ingested-at).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Protocol

from analyst.api import fixtures
from analyst.domain.dataset import DatasetSummary, RefreshResult
from analyst.domain.status import IngestionStatus

_LOG = logging.getLogger(__name__)


@dataclass
class DatasetRecord:
    """A dataset plus the API-envelope metadata the domain doesn't track."""

    summary: DatasetSummary
    file_name: str
    status: IngestionStatus = IngestionStatus.COMPLETE
    ingested_at: str | None = None
    started_at: float | None = None  # monotonic; drives simulated progress
    # Federated (connected-DB) tables are catalogued + visible.
    federated: bool = False
    # Feature 007 — a federated table whose data is ATTACHed into the store's
    # connection (scanner engine), so within-DB Q&A can run SQL against it.
    db_queryable: bool = False
    # Feature 009 — async cataloguing lifecycle for connected-DB tables:
    # "complete" | "pending" (background cataloguing) | "failed" (contained).
    catalog_status: str = "complete"

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

    # Feature 005 hooks — connection-backed datasets (routes/databases.py owns
    # the federation logic; these only add/remove the resulting records).
    def add_records(self, records: list[DatasetRecord]) -> None: ...
    def remove_records(self, names: list[str]) -> None: ...


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

    def add_records(self, records: list[DatasetRecord]) -> None:
        for record in records:
            self._records[record.name] = record

    def remove_records(self, names: list[str]) -> None:
        for name in names:
            self._records.pop(name, None)

    def ingest(self, file_name: str, content: bytes) -> list[DatasetRecord]:
        # Mirror the real engine's validation so the mock can't hide the
        # rejected-upload path (defect regression, exploratory 2026-07-02).
        if not content.strip():
            from analyst.engine.reader import EmptyFileError

            raise EmptyFileError("The file is empty — there is no data to ingest.")
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

    def __init__(self, data_dir: str, cataloguer: object = None) -> None:
        import tempfile

        from analyst.engine.store import DatasetStore
        from analyst.service.ingestion import IngestionService

        self._tempfile = tempfile
        self.store = DatasetStore(data_dir)
        # Feature 010: cataloguing sees the workspace — the service pulls the
        # current catalogs (files AND connected-DB records) on each ingest.
        self.service = IngestionService(
            self.store,
            cataloguer=cataloguer,  # type: ignore[arg-type]
            catalog_source=lambda: {
                name: record.summary.catalog for name, record in self._records.items()
            },
        )
        self._records: dict[str, DatasetRecord] = {}
        self._rehydrate()

    def _rehydrate(self) -> None:
        """Rebuild the dataset registry from the persisted store (HIGH H2).

        The DuckDB catalog + Parquet survive a restart; without this the API
        would show an empty workspace though the data is all on disk. Catalog
        entries are reloaded from their persisted sidecar when present.
        """
        from analyst.domain.dataset import DatasetSummary

        for name in self.store.datasets():
            try:
                profile = self.store.profile(name)
            except Exception:  # noqa: BLE001 - a broken relation shouldn't abort boot
                continue
            try:
                # Review #3: a corrupt/schema-drifted sidecar must NOT abort boot
                # and lose every healthy dataset — that table just loses its
                # cached catalog (it re-catalogues on demand).
                catalog = _load_catalog_sidecar(self.store.base_dir, name)
            except Exception:  # noqa: BLE001
                _LOG.warning("ignoring unreadable catalog sidecar for %r", name)
                catalog = None
            self._records[name] = DatasetRecord(
                summary=DatasetSummary(name=name, profile=profile, catalog=catalog),
                file_name=f"{name}.csv",
                status=IngestionStatus.COMPLETE,
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
        self.service.delete(name)
        self._records.pop(name, None)
        _catalog_sidecar(self.store.base_dir, name).unlink(missing_ok=True)

    def add_records(self, records: list[DatasetRecord]) -> None:
        for record in records:
            self._records[record.name] = record

    def remove_records(self, names: list[str]) -> None:
        for name in names:
            self._records.pop(name, None)

    def ingest(self, file_name: str, content: bytes) -> list[DatasetRecord]:
        # Write under the REAL file name (in a temp dir) — the service derives
        # the dataset name from the file's stem, so a NamedTemporaryFile would
        # produce garbage dataset names like "tmps9jbs9y1". SECURITY (C1): the
        # name is basename-sanitized so a `../`-laden upload can't escape the dir.
        with self._tempfile.TemporaryDirectory() as tmp_dir:
            from pathlib import Path

            tmp_path = Path(tmp_dir) / _safe_upload_name(file_name)
            tmp_path.write_bytes(content)
            result = self.service.ingest(tmp_path)
        out: list[DatasetRecord] = []
        for summary in result.datasets:
            # Persist the agent-authored catalog so it survives a restart (H2).
            _save_catalog_sidecar(self.store.base_dir, summary.name, summary.catalog)
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


def _catalog_sidecar(base_dir: object, name: str):  # noqa: ANN001
    from pathlib import Path

    return Path(str(base_dir)) / f"{name}.catalog.json"


def _save_catalog_sidecar(base_dir: object, name: str, catalog: object) -> None:
    """Persist a catalog entry so it survives a restart (HIGH H2 + cataloguer)."""
    import dataclasses
    import json

    if not dataclasses.is_dataclass(catalog) or isinstance(catalog, type):
        return
    _catalog_sidecar(base_dir, name).write_text(
        json.dumps(dataclasses.asdict(catalog)), encoding="utf-8"
    )


def _load_catalog_sidecar(base_dir: object, name: str):  # noqa: ANN001
    path = _catalog_sidecar(base_dir, name)
    if not path.exists():
        return None
    import json

    from analyst.domain.catalog import (
        CatalogEntry,
        Clarification,
        ColumnDescription,
    )
    from analyst.domain.relationships import Relationship

    data = json.loads(path.read_text(encoding="utf-8"))
    return CatalogEntry(
        table_description=data["table_description"],
        columns=tuple(ColumnDescription(**c) for c in data["columns"]),
        clarifications=tuple(
            Clarification(
                question=c["question"],
                options=tuple(c["options"]),
                column=c.get("column"),
            )
            for c in data["clarifications"]
        ),
        relationships=tuple(Relationship(**r) for r in data.get("relationships", [])),
    )


def _safe_upload_name(file_name: str) -> str:
    """Basename-only upload name (SECURITY C1) — strips any directory component
    (`../`, absolute paths, Windows separators) so a crafted filename can never
    escape the temp directory it's written into."""
    from pathlib import PurePosixPath, PureWindowsPath

    raw = (file_name or "").strip()
    # Handle both separator styles regardless of host OS.
    base = PureWindowsPath(PurePosixPath(raw).name).name.strip()
    return base or "upload.csv"
