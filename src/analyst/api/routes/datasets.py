"""Dataset routes — the feature 001/002 surface (list/get/ingest/status/
refresh/delete + catalog)."""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse

from analyst.api.deps import get_repository
from analyst.api.repository import DatasetRecord, DatasetRepository
from analyst.api.schemas import (
    CatalogEntrySchema,
    ClarificationSchema,
    DatasetProfileSchema,
    DatasetSchema,
    IngestionResultSchema,
    IngestionStatusSchema,
    NormalizationRuleSchema,
    NormalizationStateSchema,
    RefreshResultSchema,
)
from analyst.domain.normalization import UnknownNormalizationError
from analyst.engine.reader import FileTooLargeError

router = APIRouter(prefix="/api")

_UPLOAD_CHUNK = 1 << 20  # 1 MiB


def _max_upload_bytes() -> int:
    return int(os.environ.get("ANALYST_MAX_UPLOAD_BYTES", str(1_000_000_000)))


def _read_capped(file: UploadFile) -> bytes:
    """Read an upload in chunks, aborting once it exceeds the cap (HIGH H3).

    Prevents a huge (or many concurrent) upload from OOM-ing the worker before
    the size check — memory is bounded to the cap, not the attacker's file size.

    Synchronous on purpose: the upload routes are sync ``def`` so FastAPI runs
    them (and repo.ingest with any live cataloguing inside) on the threadpool,
    off the event loop — the live LLM backend drives its own loop via
    asyncio.run(), which is illegal on the event-loop thread.
    """
    cap = _max_upload_bytes()
    chunks: list[bytes] = []
    total = 0
    while chunk := file.file.read(_UPLOAD_CHUNK):
        total += len(chunk)
        if total > cap:
            raise FileTooLargeError(
                f"The upload exceeds the {cap}-byte limit for this version."
            )
        chunks.append(chunk)
    return b"".join(chunks)


def to_dataset_schema(rec: DatasetRecord) -> DatasetSchema:
    profile = rec.summary.profile
    return DatasetSchema(
        id=rec.name,
        name=rec.name,
        file_name=rec.file_name,
        status=rec.status.value,
        ingested_at=rec.ingested_at,
        row_count=profile.row_count,
        column_count=len(profile.columns),
        profile=DatasetProfileSchema.from_domain(profile),
        catalog=(
            CatalogEntrySchema.from_domain(rec.summary.catalog)
            if rec.summary.catalog
            else None
        ),
        # Feature 006 — source grouping (file/connection → table) + the
        # not-yet-queryable marking for connected-database tables.
        group=_group_and_entity(rec.name, rec.federated)[0],
        entity=_group_and_entity(rec.name, rec.federated)[1],
        source_kind="database" if rec.federated else "file",
        queryable=(not rec.federated) or getattr(rec, "db_queryable", False),
        catalog_status=rec.catalog_status,
    )


def _group_and_entity(name: str, federated: bool) -> tuple[str, str]:
    """Split a dataset name into (group, entity) for the workbench tree.

    File  `company.employees.xlsx` → ("company.xlsx", "employees")  [file+sheet]
    File  `orders.csv`             → ("orders.csv", "orders")       [single table]
    DB    `sales_db.orders`        → ("sales_db", "orders")         [conn+table]
    """
    parts = name.split(".")
    if federated:
        return parts[0], ".".join(parts[1:]) or parts[0]
    if len(parts) >= 3:  # <stem>.<sheet>.<ext>
        return f"{parts[0]}.{parts[-1]}", ".".join(parts[1:-1])
    if len(parts) == 2:  # <stem>.<ext>
        return name, parts[0]
    return name, name


def _require(repo: DatasetRepository, name: str) -> DatasetRecord:
    rec = repo.get_dataset(name)
    if rec is None:
        raise HTTPException(404, f"Dataset '{name}' not found")
    return rec


@router.get("/datasets")
def list_datasets(repo: DatasetRepository = Depends(get_repository)) -> list[dict]:
    return [to_dataset_schema(r).dump() for r in repo.list_datasets()]


@router.get("/datasets/{name}")
def get_dataset(name: str, repo: DatasetRepository = Depends(get_repository)) -> dict:
    return to_dataset_schema(_require(repo, name)).dump()


@router.post("/datasets/ingest")
def ingest(file: UploadFile, repo: DatasetRepository = Depends(get_repository)) -> dict:
    content = _read_capped(file)
    records = repo.ingest(file.filename or "upload.csv", content)
    return IngestionResultSchema(
        datasets=[to_dataset_schema(r) for r in records]
    ).dump()


@router.get("/ingestion/{name}/status")
def ingestion_status(
    name: str, repo: DatasetRepository = Depends(get_repository)
) -> dict:
    status, phase, progress = repo.status(name)
    return IngestionStatusSchema(
        dataset=name, status=status.value, phase=phase, progress=progress
    ).dump()


@router.delete("/datasets/{name}", status_code=204)
def delete_dataset(
    name: str, repo: DatasetRepository = Depends(get_repository)
) -> None:
    _require(repo, name)
    repo.delete(name)


@router.post("/datasets/{name}/refresh")
def refresh_dataset(
    name: str, file: UploadFile, repo: DatasetRepository = Depends(get_repository)
) -> dict:
    _require(repo, name)
    content = _read_capped(file)
    result = repo.refresh(name, file.filename or f"{name}.csv", content)
    return RefreshResultSchema(
        dataset_name=result.dataset_name,
        replaced=result.replaced,
        version=result.version,
        clarification=(
            ClarificationSchema.from_domain(result.clarification)
            if result.clarification
            else None
        ),
        profile=(
            DatasetProfileSchema.from_domain(result.profile) if result.profile else None
        ),
    ).dump()


@router.get("/datasets/{name}/export")
def export_dataset_route(
    name: str,
    format: str = "csv",
    repo: DatasetRepository = Depends(get_repository),
) -> FileResponse:
    """Feature 014: full-fidelity local export of the dataset AS QUERIES SEE
    IT (normalization overlay included). Never truncated by the display cap."""
    import tempfile

    from analyst.engine.exports import FORMATS, export_dataset

    _require(repo, name)
    if format not in FORMATS:
        raise HTTPException(400, f"Unsupported export format '{format}'")
    store = getattr(repo, "store", None)
    if store is None:
        raise HTTPException(400, "Exports need the real data store")
    path = tempfile.NamedTemporaryFile(suffix=f".{format}", delete=False).name
    export_dataset(store, name, format, path)
    media = {
        "csv": "text/csv",
        "parquet": "application/vnd.apache.parquet",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }[format]
    return FileResponse(
        path,
        media_type=media,
        filename=f"{name}.{format}",
        content_disposition_type="attachment",
    )


def _normalization_state(repo: DatasetRepository, name: str) -> dict:
    proposals, applied = repo.normalization(name)
    return NormalizationStateSchema(
        proposals=[NormalizationRuleSchema.from_domain(r) for r in proposals],
        applied=[NormalizationRuleSchema.from_domain(r) for r in applied],
    ).dump()


@router.get("/datasets/{name}/normalization")
def get_normalization(
    name: str, repo: DatasetRepository = Depends(get_repository)
) -> dict:
    _require(repo, name)
    return _normalization_state(repo, name)


@router.post("/datasets/{name}/normalization/{rule_id}/{action}")
def act_on_normalization(
    name: str,
    rule_id: str,
    action: str,
    repo: DatasetRepository = Depends(get_repository),
) -> dict:
    """Approve, dismiss, or revoke one rule; returns the updated state so the
    UI refreshes in a single round-trip. The ONLY paths that apply a rule —
    the charter's never-silently-applied gate lives here."""
    _require(repo, name)
    handlers = {
        "approve": repo.approve_normalization,
        "dismiss": repo.dismiss_normalization,
        "revoke": repo.revoke_normalization,
    }
    if action not in handlers:
        raise HTTPException(404, f"Unknown action '{action}'")
    try:
        handlers[action](name, rule_id)
    except UnknownNormalizationError:
        raise HTTPException(
            404, f"Normalization rule '{rule_id}' not found for '{name}'"
        ) from None
    return _normalization_state(repo, name)


@router.get("/catalog")
def get_catalog(repo: DatasetRepository = Depends(get_repository)) -> dict:
    return {
        name: CatalogEntrySchema.from_domain(entry).dump()  # type: ignore[arg-type]
        for name, entry in repo.catalog().items()
    }
