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
from analyst.api.routes import auth, databases, datasets, qa, system
from analyst.engine.reader import (
    EmptyFileError,
    FileTooLargeError,
    MalformedFileError,
    UnsupportedFormatError,
)


def fixtures_enabled() -> bool:
    """Fixtures are OPT-IN (ANALYST_FIXTURES=1); the real store is the default."""
    return os.environ.get("ANALYST_FIXTURES", "0") == "1"


def catalog_mode() -> str:
    """How dataset descriptions are produced — surfaced on /api/health so the
    UI can SAY when cataloguing runs without AI instead of degrading silently.

    - "canned"  → fixtures mode (curated demo descriptions)
    - "replay"  → recorded cassette (deterministic tests)
    - "live"    → real Claude Agent SDK calls (the app)
    - "off"     → no model: profile-derived descriptions only
    """
    if fixtures_enabled():
        return "canned"
    if os.environ.get("ANALYST_CATALOG_CASSETTE"):
        return "replay"
    if os.environ.get("ANALYST_CATALOG") == "live":
        return "live"
    return "off"


def build_cataloguer() -> object | None:
    """The agent cataloguer for real ingestion — OPT-IN so CI/tests stay
    deterministic and offline (golden-path fix M3). Modes per catalog_mode();
    "off" (and fixtures' "canned") mean no cataloguer: profiles only."""
    from analyst.agentic.cataloguer import Cataloguer
    from analyst.agentic.gateway import LLMGateway, ReplayBackend

    mode = catalog_mode()
    if mode == "replay":
        return Cataloguer(
            LLMGateway(ReplayBackend(os.environ["ANALYST_CATALOG_CASSETTE"]))
        )
    if mode == "live":
        from analyst.agentic.claude_backend import ClaudeAgentBackend

        return Cataloguer(LLMGateway(ClaudeAgentBackend()))
    return None


def _build_repository() -> DatasetRepository:
    if fixtures_enabled():
        return FixtureRepository()
    return StoreRepository(
        os.environ.get("ANALYST_DATA_DIR", ".analyst-data"),
        cataloguer=build_cataloguer(),
    )


def create_app(repo: DatasetRepository | None = None) -> FastAPI:
    app = FastAPI(title="analyst", version="0.1.0")
    # Pin CORS to the deployment origin when known (ANALYST_PUBLIC_URL); the
    # wildcard is a dev convenience only. Credentials are not enabled, so the
    # cookie is never exposed cross-origin regardless.
    public_url = os.environ.get("ANALYST_PUBLIC_URL")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[public_url] if public_url else ["*"],
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
    app.include_router(databases.router)
    app.include_router(datasets.router)
    app.include_router(qa.router)
    app.include_router(system.router)
    _mount_web(app)
    return app


def _mount_web(app: FastAPI) -> None:
    """Serve the built frontend from this process (single-image deploy).

    ANALYST_WEB_DIST names the Vite build output; unset, the repo-relative
    ``frontend/dist`` is used when it exists. Mounted after the routers, so
    ``/api/*`` always wins; no dist → API-only (the dev setup, where Vite
    proxies to us)."""
    from pathlib import Path

    from fastapi.staticfiles import StaticFiles

    configured = os.environ.get("ANALYST_WEB_DIST")
    dist = (
        Path(configured)
        if configured
        else Path(__file__).resolve().parents[3] / "frontend" / "dist"
    )
    if (dist / "index.html").is_file():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="web")


app = create_app()
