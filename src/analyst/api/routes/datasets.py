"""Dataset routes — the feature 001/002 surface (list/get/ingest/status/
refresh/delete + catalog)."""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from analyst.api.deps import get_repository
from analyst.api.repository import DatasetRecord, DatasetRepository
from analyst.api.schemas import (
    CatalogEntrySchema,
    ClarificationSchema,
    DatasetProfileSchema,
    DatasetSchema,
    IngestionResultSchema,
    IngestionStatusSchema,
    RefreshResultSchema,
)
from analyst.engine.reader import FileTooLargeError

router = APIRouter(prefix="/api")

_UPLOAD_CHUNK = 1 << 20  # 1 MiB


def _max_upload_bytes() -> int:
    return int(os.environ.get("ANALYST_MAX_UPLOAD_BYTES", str(1_000_000_000)))


async def _read_capped(file: UploadFile) -> bytes:
    """Read an upload in chunks, aborting once it exceeds the cap (HIGH H3).

    Prevents a huge (or many concurrent) upload from OOM-ing the worker before
    the size check — memory is bounded to the cap, not the attacker's file size.
    """
    cap = _max_upload_bytes()
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(_UPLOAD_CHUNK):
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
        # Feature 006 — source grouping + the not-yet-queryable marking for
        # connected-database tables (federated records).
        group=rec.name.split(".", 1)[0],
        source_kind="database" if rec.federated else "file",
        queryable=not rec.federated,
    )


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
async def ingest(
    file: UploadFile, repo: DatasetRepository = Depends(get_repository)
) -> dict:
    content = await _read_capped(file)
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
async def refresh_dataset(
    name: str, file: UploadFile, repo: DatasetRepository = Depends(get_repository)
) -> dict:
    _require(repo, name)
    content = await _read_capped(file)
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


@router.get("/catalog")
def get_catalog(repo: DatasetRepository = Depends(get_repository)) -> dict:
    return {
        name: CatalogEntrySchema.from_domain(entry).dump()  # type: ignore[arg-type]
        for name, entry in repo.catalog().items()
    }
