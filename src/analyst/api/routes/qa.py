"""Q&A routes — PROVISIONAL (canned) until feature 003 lands the real
NL→SQL planner. Feature 003's session owns this file and analyst/agentic."""

from __future__ import annotations

from fastapi import APIRouter

from analyst.api import qa
from analyst.api.schemas import QueryRequest, RespondRequest

router = APIRouter(prefix="/api")


@router.post("/query")
def submit_query(body: QueryRequest) -> dict:
    return qa.submit_query(body.question).dump()


@router.post("/query/{query_id}/respond")
def respond_query(query_id: str, body: RespondRequest) -> dict:
    return qa.respond(query_id, body.selected_options).dump()
