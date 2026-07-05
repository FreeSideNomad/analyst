"""Shared AC-14 fixture: ingest two related files, discover the relationship,
and plan a join question through the planner. Used by the acceptance handler
(ReplayBackend) and the live cassette recorder (RecordingBackend) so their
prompts — and therefore the cassette key — match exactly.
"""

from __future__ import annotations

from pathlib import Path

from analyst.agentic.gateway import LLMBackend, LLMGateway
from analyst.agentic.planner import QueryPlanner
from analyst.domain.dataset import DatasetSummary
from analyst.domain.query import QueryPlan, query_table_from_summary
from analyst.engine.store import DatasetStore
from analyst.service.ingestion import IngestionService

REPO_ROOT = Path(__file__).resolve().parent.parent
JOIN_CASSETTE = REPO_ROOT / "tests" / "cassettes" / "join_planner.json"

# customer_id is OPTIONAL: row 3 has none — a LEFT join must keep it.
ORDERS_CSV = "order_id,customer_id,quantity\n1,10,2\n2,20,1\n3,,5\n4,10,3\n"
CUSTOMERS_CSV = "customer_id,region\n10,North\n20,South\n"
JOIN_QUESTION = "What is the total order quantity per customer region?"


def build_plan(tmp_dir: Path, backend: LLMBackend) -> tuple[QueryPlan, object]:
    """Ingest the two files, discover relationships, plan the join question."""
    store = DatasetStore(base_dir=tmp_dir / "store")
    service = IngestionService(store)
    for name, content in (("orders.csv", ORDERS_CSV), ("customers.csv", CUSTOMERS_CSV)):
        path = tmp_dir / name
        path.write_text(content, encoding="utf-8")
        service.ingest(path)
    relationships = store.discover_relationships()
    summaries = [
        DatasetSummary(name=name, profile=store.profile(name))
        for name in sorted(store.datasets())
    ]
    tables = tuple(query_table_from_summary(s) for s in summaries)
    planner = QueryPlanner(LLMGateway(backend))
    plan = planner.plan(JOIN_QUESTION, tables, relationships)  # type: ignore[arg-type]
    return plan, relationships
