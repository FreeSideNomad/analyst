"""Record the feature-017 planner cassette (run ONCE, live).

uv run python scripts/record_cross_db_cassette.py
"""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

from analyst.agentic.claude_backend import ClaudeAgentBackend
from analyst.agentic.gateway import LLMGateway, RecordingBackend
from analyst.agentic.planner import QueryPlanner
from analyst.api.qa import PlannerQAService
from analyst.api.repository import StoreRepository
from analyst.api.routes.databases import DatabaseManager
from analyst.domain.connection import ConnectionSpec, DatabaseEngine
from scripts.make_cross_dbs import make as make_dbs

REPO = Path(__file__).resolve().parent.parent
CASSETTE = REPO / "tests" / "cassettes" / "cross_db_planner.json"


def drain(repo: StoreRepository) -> None:
    for _ in range(100):
        if all(r.catalog_status != "pending" for r in repo.list_datasets()):
            return
        time.sleep(0.1)


def restart_phase(qa: PlannerQAService) -> None:
    """Mirror the board's restart scenario: vault-persisted connect, then a
    rebuilt repo + manager restored from credentials, then the question."""
    import os

    from analyst.engine.credentials import CredentialVault

    os.environ["ANALYST_SECRET_KEY"] = "cross-db-acceptance-key"
    with tempfile.TemporaryDirectory() as td:
        crm, billing = make_dbs(Path(td) / "dbs")
        repo = StoreRepository(td + "/data")
        manager = DatabaseManager(
            repo, vault=CredentialVault("cross-db-acceptance-key")
        )
        for name, path in (("crm", crm), ("billing", billing)):
            manager.connect(
                ConnectionSpec(name=name, engine=DatabaseEngine.SQLITE, path=str(path))
            )
        drain(repo)
        repo2 = StoreRepository(td + "/data")
        manager2 = DatabaseManager(
            repo2, vault=CredentialVault("cross-db-acceptance-key")
        )
        manager2.restore_persisted()
        drain(repo2)
        a = qa.submit("Which customer segment generates the most revenue?", repo2)
        print("post-restart:", getattr(a, "summary", a))


def main() -> None:
    qa = PlannerQAService(
        QueryPlanner(LLMGateway(RecordingBackend(ClaudeAgentBackend(), CASSETTE)))
    )
    with tempfile.TemporaryDirectory() as td:
        crm, billing = make_dbs(Path(td) / "dbs")
        repo = StoreRepository(td + "/data")
        manager = DatabaseManager(repo)
        for name, path in (("crm", crm), ("billing", billing)):
            manager.connect(
                ConnectionSpec(name=name, engine=DatabaseEngine.SQLITE, path=str(path))
            )
        drain(repo)

        a = qa.submit("Which customer segment generates the most revenue?", repo)
        print("segment:", getattr(a, "summary", a))
        print("  sql:", getattr(getattr(a, "trust_trail", None), "sql", None))

        b = qa.submit("How many customers are there?", repo)
        print("count:", getattr(b, "summary", b))

        manager.detach("billing")
        c = qa.submit("Which customer segment generates the most revenue?", repo)
        print("detached:", getattr(c, "abstain", None), "|", getattr(c, "summary", c))

    restart_phase(qa)
    print("cassette entries:", len(json.loads(CASSETTE.read_text())))


if __name__ == "__main__":
    main()
