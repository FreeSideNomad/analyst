"""System routes — health + the test-only fixture reset."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from analyst.api.repository import FixtureRepository
from analyst.api.routes import auth

router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict:
    from analyst.api.app import fixtures_enabled

    return {"ok": True, "fixtures": fixtures_enabled(), "qa": "provisional"}


@router.post("/_reset", status_code=204, include_in_schema=False)
def reset_fixtures(request: Request) -> None:
    """Test-only: restore the seeded fixture workspace between e2e scenarios."""
    holder = request.app.state.repo_holder
    if not isinstance(holder["repo"], FixtureRepository):
        raise HTTPException(404, "reset is only available in fixtures mode")
    holder["repo"] = FixtureRepository()
    # Feature 004: also drop per-workspace repos + auth state (users/sessions).
    holder.pop("workspaces", None)
    auth.reset_state(request.app)
