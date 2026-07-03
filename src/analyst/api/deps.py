"""Shared FastAPI dependencies for the route modules.

The repository lives in a swappable holder on ``app.state`` so the test-only
reset endpoint can restore the fixture workspace between e2e scenarios.
"""

from __future__ import annotations

from fastapi import Request

from analyst.api.repository import DatasetRepository


def get_repository(request: Request) -> DatasetRepository:
    return request.app.state.repo_holder["repo"]
