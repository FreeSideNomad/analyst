"""Q&A routes (feature 003) — thin delegation to the QAService seam.

The service is built lazily from the active repository and held on
``app.state.qa_holder``: fixtures repo -> the canned deterministic path,
real store -> the agentic planner (live, or replayed when
``ANALYST_QA_CASSETTE`` is set). The wire contract is feature 002's, unchanged.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from analyst.api.deps import get_repository
from analyst.api.qa import QAService, build_qa_service
from analyst.api.repository import DatasetRepository
from analyst.api.schemas import QueryRequest, RespondRequest

router = APIRouter(prefix="/api")


def get_qa_service(request: Request) -> QAService:
    holder = getattr(request.app.state, "qa_holder", None)
    if holder is None:
        holder = {"service": None}
        request.app.state.qa_holder = holder
    if holder.get("service") is None:
        holder["service"] = build_qa_service(request.app.state.repo_holder["repo"])
    service: QAService = holder["service"]
    return service


@router.post("/query")
def submit_query(
    body: QueryRequest,
    repo: DatasetRepository = Depends(get_repository),
    service: QAService = Depends(get_qa_service),
) -> dict:
    return service.submit(body.question, repo).dump()


@router.post("/query/{query_id}/respond")
def respond_query(
    query_id: str,
    body: RespondRequest,
    repo: DatasetRepository = Depends(get_repository),
    service: QAService = Depends(get_qa_service),
) -> dict:
    answer = service.respond(query_id, body.selected_options, repo)
    if answer is None:
        raise HTTPException(404, f"Unknown query id '{query_id}'")
    return answer.dump()
