"""Record the container-mode turns for feature 012 (run ONCE, live).

The container runs FULL replay mode (ANALYST_CATALOG_CASSETTE), so every
agent turn of the browser journey needs a recording made along the SAME
path the container takes: live cataloguing of the Ames sample, then
guidance whose prompt embeds that agent-written catalog.
Appends to tests/cassettes/models_guidance.json.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

os.environ.setdefault("ANALYST_ML_CACHE", "tests/.ml_cache")

from analyst.agentic.cataloguer import Cataloguer
from analyst.agentic.claude_backend import ClaudeAgentBackend
from analyst.agentic.gateway import LLMGateway, RecordingBackend
from analyst.agentic.models import ModelGuide
from analyst.api.repository import StoreRepository

REPO = Path(__file__).resolve().parent.parent
CASSETTE = REPO / "tests" / "cassettes" / "models_guidance.json"


def main() -> None:
    backend = RecordingBackend(ClaudeAgentBackend(), CASSETTE)
    gateway = LLMGateway(backend)
    with tempfile.TemporaryDirectory() as td:
        repo = StoreRepository(
            td + "/data",
            cataloguer=Cataloguer(gateway),
            model_guide=ModelGuide(gateway),
        )
        record = repo.add_sample("ames")  # records the cataloguing turn
        catalog = record.summary.catalog
        print("catalogued:", (catalog.table_description or "")[:100])
        task = repo.create_model_task("ames.csv", "SalePrice")
        print("guidance features:", len(task["proposed"]))
    print("cassette entries:", len(json.loads(CASSETTE.read_text())))


if __name__ == "__main__":
    main()
