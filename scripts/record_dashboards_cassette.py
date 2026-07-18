"""Record the feature-015 dashboards cassette (run ONCE, live).

    uv run python scripts/record_dashboards_cassette.py

Replays the exact acceptance-board assembly flows with a RecordingBackend
around the live Claude Agent SDK. The board's workspace must match this
script byte-for-byte (same files, enrich-only catalogs) so replay keys hit.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from analyst.agentic.claude_backend import ClaudeAgentBackend
from analyst.agentic.dashboards import DashboardAssembler
from analyst.agentic.gateway import LLMGateway, RecordingBackend
from analyst.api.repository import StoreRepository

REPO = Path(__file__).resolve().parent.parent
CASSETTE = REPO / "tests" / "cassettes" / "dashboards.json"

SALES = (
    "region,product,amount\n"
    "East,widget,10\nEast,gadget,20\nWest,widget,30\n"
    "West,gadget,40\nNorth,widget,50\n"
)
STAFF = "employee,dept\nAna,ops\nBo,sales\n"


def main() -> None:
    assembler = DashboardAssembler(
        LLMGateway(RecordingBackend(ClaudeAgentBackend(), CASSETTE))
    )
    with tempfile.TemporaryDirectory() as td:
        repo = StoreRepository(td + "/d", assembler=assembler)
        repo.ingest("sales.csv", SALES.encode())
        repo.ingest("staff.csv", STAFF.encode())

        out = repo.create_dashboard("a sales and staffing overview dashboard")
        dash = out["dashboard"]
        assert dash is not None, "expected an assembled dashboard"
        print("assembled:", dash.name)
        for w in dash.widgets:
            print("  widget:", w.widget_id, "| source:", w.source, "|", w.sql[:80])
        print("  filters:", [f.column for f in dash.filters])

        vague = repo.create_dashboard("a dashboard")
        if vague["clarification"] is None:
            print(
                "WARNING: vague request did NOT clarify — re-record with a vaguer phrasing"
            )
        else:
            print("clarified:", vague["clarification"].question)

        edited = repo.edit_dashboard(
            dash.dashboard_id, "add a widget showing the row count by region"
        )
        print("edited widgets:", [w.widget_id for w in edited["dashboard"].widgets])

    print("cassette:", CASSETTE.name, "entries:", len(json.loads(CASSETTE.read_text())))


if __name__ == "__main__":
    main()
