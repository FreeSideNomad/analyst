"""FastAPI application — serves the aligned contract (see CONTRACT.md).

Thin assembly: repository selection, domain-error → HTTP mapping, and the
per-area routers under ``analyst.api.routes`` (each parallel feature session
owns its own route module — see docs/PARALLEL_PLAN.md).

Repository is chosen by env: the real DuckDB store is the DEFAULT
(ANALYST_DATA_DIR, default .analyst-data). Set ANALYST_FIXTURES=1 to opt into
the in-memory Python mock (demos, deterministic e2e) — retained, not default.
"""

from __future__ import annotations

import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from analyst.api.repository import (
    DatasetRepository,
    FixtureRepository,
    StoreRepository,
)
from analyst.api.routes import auth, datasets, qa, system
from analyst.engine.reader import (
    EmptyFileError,
    FileTooLargeError,
    MalformedFileError,
    UnsupportedFormatError,
)


def fixtures_enabled() -> bool:
    """Fixtures are OPT-IN (ANALYST_FIXTURES=1); the real store is the default."""
    return os.environ.get("ANALYST_FIXTURES", "0") == "1"


def _build_repository() -> DatasetRepository:
    if fixtures_enabled():
        return FixtureRepository()
    return StoreRepository(os.environ.get("ANALYST_DATA_DIR", ".analyst-data"))


def create_app(repo: DatasetRepository | None = None) -> FastAPI:
    app = FastAPI(title="analyst", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Swappable holder — the test-only reset endpoint replaces the repo.
    app.state.repo_holder = {"repo": repo or _build_repository()}

    # Domain validation errors carry user-facing messages (AC-11/14/15/21 of
    # feature 001) — surface them as clean 4xx, never as 500s + tracebacks.
    def _rejection(status_code: int):
        def handler(_request: Request, exc: Exception) -> JSONResponse:
            return JSONResponse(status_code=status_code, content={"detail": str(exc)})

        return handler

    for error_type in (EmptyFileError, UnsupportedFormatError, MalformedFileError):
        app.add_exception_handler(error_type, _rejection(400))
    app.add_exception_handler(FileTooLargeError, _rejection(413))

    # Feature 004: session enforcement — a NO-OP until a login method is
    # configured via env (see analyst.api.routes.auth.auth_enabled).
    auth.install(app)

    app.include_router(auth.router)
    app.include_router(auth.workspaces_router)
    app.include_router(datasets.router)
    app.include_router(qa.router)
    app.include_router(system.router)
    return app


app = create_app()
