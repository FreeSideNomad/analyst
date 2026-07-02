"""FastAPI application — serves the aligned contract (see CONTRACT.md).

Repository is chosen by env: the real DuckDB store is the DEFAULT
(ANALYST_DATA_DIR, default .analyst-data). Set ANALYST_FIXTURES=1 to opt into
the in-memory Python mock (demos, deterministic e2e) — retained, not default.
"""

from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from analyst.api import qa
from analyst.api.repository import (
    DatasetRecord,
    DatasetRepository,
    FixtureRepository,
    StoreRepository,
)
from analyst.api.schemas import (
    CatalogEntrySchema,
    ClarificationSchema,
    DatasetProfileSchema,
    DatasetSchema,
    IngestionResultSchema,
    IngestionStatusSchema,
    QueryRequest,
    RefreshResultSchema,
    RespondRequest,
)


def fixtures_enabled() -> bool:
    """Fixtures are OPT-IN (ANALYST_FIXTURES=1); the real store is the default."""
    return os.environ.get("ANALYST_FIXTURES", "0") == "1"


def _build_repository() -> DatasetRepository:
    if fixtures_enabled():
        return FixtureRepository()
    return StoreRepository(os.environ.get("ANALYST_DATA_DIR", ".analyst-data"))


def _to_dataset_schema(rec: DatasetRecord) -> DatasetSchema:
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
    )


def create_app(repo: DatasetRepository | None = None) -> FastAPI:
    app = FastAPI(title="analyst", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    repository: DatasetRepository = repo or _build_repository()

    # ---- feature 001: datasets / profiling / catalog --------------------- #
    @app.get("/api/datasets")
    def list_datasets() -> list[dict]:
        return [_to_dataset_schema(r).dump() for r in repository.list_datasets()]

    @app.get("/api/datasets/{name}")
    def get_dataset(name: str) -> dict:
        rec = repository.get_dataset(name)
        if rec is None:
            raise HTTPException(404, f"Dataset '{name}' not found")
        return _to_dataset_schema(rec).dump()

    @app.post("/api/datasets/ingest")
    async def ingest(file: UploadFile) -> dict:
        content = await file.read()
        records = repository.ingest(file.filename or "upload.csv", content)
        return IngestionResultSchema(
            datasets=[_to_dataset_schema(r) for r in records]
        ).dump()

    @app.get("/api/ingestion/{name}/status")
    def ingestion_status(name: str) -> dict:
        status, phase, progress = repository.status(name)
        return IngestionStatusSchema(
            dataset=name, status=status.value, phase=phase, progress=progress
        ).dump()

    @app.delete("/api/datasets/{name}", status_code=204)
    def delete_dataset(name: str) -> None:
        if repository.get_dataset(name) is None:
            raise HTTPException(404, f"Dataset '{name}' not found")
        repository.delete(name)

    @app.post("/api/datasets/{name}/refresh")
    async def refresh_dataset(name: str, file: UploadFile) -> dict:
        if repository.get_dataset(name) is None:
            raise HTTPException(404, f"Dataset '{name}' not found")
        content = await file.read()
        result = repository.refresh(name, file.filename or f"{name}.csv", content)
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
                DatasetProfileSchema.from_domain(result.profile)
                if result.profile
                else None
            ),
        ).dump()

    @app.get("/api/catalog")
    def get_catalog() -> dict:
        return {
            name: CatalogEntrySchema.from_domain(entry).dump()  # type: ignore[arg-type]
            for name, entry in repository.catalog().items()
        }

    # ---- feature 002: Q&A (provisional) ---------------------------------- #
    @app.post("/api/query")
    def submit_query(body: QueryRequest) -> dict:
        return qa.submit_query(body.question).dump()

    @app.post("/api/query/{query_id}/respond")
    def respond_query(query_id: str, body: RespondRequest) -> dict:
        return qa.respond(query_id, body.selected_options).dump()

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True, "fixtures": fixtures_enabled(), "qa": "provisional"}

    return app


app = create_app()
