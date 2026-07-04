"""Shared FastAPI dependencies for the route modules.

The repository lives in a swappable holder on ``app.state`` so the test-only
reset endpoint can restore the fixture workspace between e2e scenarios.

Workspace scoping (feature 004): when the session middleware has attached an
authenticated session, the repository is chosen per the session's ACTIVE
WORKSPACE — a fresh-seeded ``FixtureRepository`` per workspace in fixtures
mode, or a ``StoreRepository`` under ``<data_dir>/workspaces/<id>`` in store
mode. Without auth configured there is no session and the single default
repository is returned — the pre-004 behavior, unchanged.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import HTTPException, Request

from analyst.api.repository import DatasetRepository


def _workspace_repository(workspace_id: str) -> DatasetRepository:
    from analyst.api.app import fixtures_enabled
    from analyst.api.repository import FixtureRepository, StoreRepository

    if fixtures_enabled():
        return FixtureRepository()
    data_dir = os.environ.get("ANALYST_DATA_DIR", ".analyst-data")
    return StoreRepository(str(Path(data_dir) / "workspaces" / workspace_id))


def get_repository(request: Request) -> DatasetRepository:
    holder = request.app.state.repo_holder
    session = getattr(request.state, "auth_session", None)
    if session is None:
        repo: DatasetRepository = holder["repo"]
        return repo
    if session.workspace_id is None:
        raise HTTPException(403, "No workspace has been assigned to you yet")
    repos: dict[str, DatasetRepository] = holder.setdefault("workspaces", {})
    if session.workspace_id not in repos:
        repos[session.workspace_id] = _workspace_repository(session.workspace_id)
    return repos[session.workspace_id]
