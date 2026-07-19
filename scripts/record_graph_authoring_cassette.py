"""Record the feature-019 authoring cassette (run ONCE, live).

PYTHONPATH=. uv run python scripts/record_graph_authoring_cassette.py

Mirrors acceptance/e2e_019.py byte-for-byte: the same seeded Postgres
container, the same connected workspace, the same question — so the
replayed prompt hash matches both the board and the container journey.
Also authors on the UPLOADS workspace; if that prompt differs (it should
not — same aliases, rows, types), the cassette simply carries both turns.
"""

from __future__ import annotations

import json
import os
import tempfile

os.environ.setdefault("ANALYST_ML_CACHE", "tests/.ml_cache")
os.environ.setdefault("ANALYST_SECRET_KEY", "e2e-019-passphrase")

from acceptance.e2e_019 import (
    _PG_PORT,
    CASSETTE,
    QUESTION,
    _ensure_seeded_postgres,
)
from analyst.agentic.claude_backend import ClaudeAgentBackend
from analyst.agentic.gateway import LLMGateway, RecordingBackend
from analyst.agentic.graphauthor import GraphAuthor
from analyst.api.repository import StoreRepository
from analyst.api.routes.databases import DatabaseManager
from analyst.domain.connection import ConnectionSpec, DatabaseEngine
from analyst.engine.credentials import CredentialVault


def _drain(repo: StoreRepository) -> None:
    import time

    for _ in range(600):
        if all(r.catalog_status != "pending" for r in repo.list_datasets()):
            return
        time.sleep(0.2)


def main() -> None:
    author = GraphAuthor(LLMGateway(RecordingBackend(ClaudeAgentBackend(), CASSETTE)))
    _ensure_seeded_postgres()
    with tempfile.TemporaryDirectory() as td:
        repo = StoreRepository(td + "/data", graph_author=author)
        DatabaseManager(repo, vault=CredentialVault("e2e-019-passphrase")).connect(
            ConnectionSpec(
                name="berka",
                engine=DatabaseEngine.POSTGRES,
                host="127.0.0.1",
                port=_PG_PORT,
                database="berka",
                user="postgres",
                password="e2e",
            )
        )
        _drain(repo)
        task = repo.author_relational_task(QUESTION)
        print("connected-path authored:", task["task_id"])
        print("  entity:", task["entity_table"], "hidden:", task["hidden_columns"])
        print("  cutoffs:", task["val_cutoff"], task["test_cutoff"])
        print("  label:", task["label_sql"])
    with tempfile.TemporaryDirectory() as td:
        repo = StoreRepository(td + "/data", graph_author=author)
        repo.add_relational_bundle()
        task = repo.author_relational_task(QUESTION)
        print("uploads-path authored:", task["task_id"])
        print("  hidden:", task["hidden_columns"])
    print("cassette entries:", len(json.loads(open(CASSETTE).read())))


if __name__ == "__main__":
    main()
