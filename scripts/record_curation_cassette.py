"""Record the feature-016 curation + planner cassettes (run ONCE, live).

    uv run python scripts/record_curation_cassette.py

Replays the exact acceptance-board flows with a RecordingBackend around the
live Claude Agent SDK, so the board's ReplayBackend finds every prompt.
Requires the Claude Code subscription login (host) — same as other cassettes.
"""

from __future__ import annotations

import dataclasses
import tempfile
from pathlib import Path

from analyst.agentic.claude_backend import ClaudeAgentBackend
from analyst.agentic.curation import Curator
from analyst.agentic.gateway import LLMGateway, RecordingBackend
from analyst.agentic.planner import QueryPlanner
from analyst.api.qa import PlannerQAService
from analyst.api.repository import StoreRepository
from analyst.domain.catalog import Clarification

REPO = Path(__file__).resolve().parent.parent
CURATION = REPO / "tests" / "cassettes" / "curation.json"
PLANNER = REPO / "tests" / "cassettes" / "curation_planner.json"

ORDERS = (
    "order_id,status,amount\n"
    "O1,fulfilled,10\nO2,unfulfilled,20\nO3,fulfilled,30\n"
    "O4,unfulfilled,40\nO5,fulfilled,50\nO6,fulfilled,60\n"
)
DATED = (
    "order_id,order_date,amount\nO1,2026-01-05,10\nO2,2026-02-06,20\nO3,2026-03-07,30\n"
)
CLARIFICATION = Clarification(
    question="What does the 'status' column describe?",
    options=(
        "Account/subscription state of the customer",
        "Fulfillment state of a sale or order",
        "Payment state (paid/pending/failed)",
    ),
    column="status",
)


def seed(repo: StoreRepository, text: str, clarify: bool) -> str:
    (rec,) = repo.ingest("orders.csv", text.encode())
    entry = rec.summary.catalog
    if clarify:
        entry = dataclasses.replace(entry, clarifications=(CLARIFICATION,))
    repo.attach_catalog(rec.name, entry)
    return rec.name


def main() -> None:
    curator = Curator(LLMGateway(RecordingBackend(ClaudeAgentBackend(), CURATION)))

    with tempfile.TemporaryDirectory() as td:  # (a) option answer + planner turn
        repo = StoreRepository(td + "/d", curator=curator)
        name = seed(repo, ORDERS, clarify=True)
        repo.answer_clarification(
            name, "status", "Fulfillment state of a sale or order"
        )
        print(
            "a:",
            next(
                c
                for c in repo.get_dataset(name).summary.catalog.columns
                if c.name == "status"
            ).description,
        )

        qa = PlannerQAService(
            QueryPlanner(LLMGateway(RecordingBackend(ClaudeAgentBackend(), PLANNER)))
        )
        answer = qa.submit("Which orders are not yet fulfilled?", repo)
        print("planner:", getattr(answer, "summary", answer))

    with tempfile.TemporaryDirectory() as td:  # (b) free-form answer
        repo = StoreRepository(td + "/d", curator=curator)
        name = seed(repo, ORDERS, clarify=True)
        repo.answer_clarification(name, "status", "Stage of the returns process")
        print(
            "b:",
            next(
                c
                for c in repo.get_dataset(name).summary.catalog.columns
                if c.name == "status"
            ).description,
        )

    with tempfile.TemporaryDirectory() as td:  # (c)+(d) corrections
        repo = StoreRepository(td + "/d", curator=curator)
        name = seed(repo, DATED, clarify=False)
        repo.suggest_correction(
            name, "order_date", "This is the settlement date, not the order date"
        )
        print(
            "c:",
            next(
                c
                for c in repo.get_dataset(name).summary.catalog.columns
                if c.name == "order_date"
            ).description,
        )
        repo.suggest_correction(name, None, "These are wholesale transactions only")
        print("d:", repo.get_dataset(name).summary.catalog.table_description)

    print("cassettes:", CURATION.name, PLANNER.name)


if __name__ == "__main__":
    main()
