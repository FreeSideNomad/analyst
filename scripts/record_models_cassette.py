"""Record the feature-012 guidance cassette (run ONCE, live).

PYTHONPATH=. uv run python scripts/record_models_cassette.py
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

os.environ.setdefault("ANALYST_ML_CACHE", "tests/.ml_cache")

from analyst.agentic.claude_backend import ClaudeAgentBackend
from analyst.agentic.gateway import LLMGateway, RecordingBackend
from analyst.agentic.models import ModelGuide
from analyst.api.repository import StoreRepository

REPO = Path(__file__).resolve().parent.parent
CASSETTE = REPO / "tests" / "cassettes" / "models_guidance.json"


def main() -> None:
    guide = ModelGuide(LLMGateway(RecordingBackend(ClaudeAgentBackend(), CASSETTE)))
    with tempfile.TemporaryDirectory() as td:
        repo = StoreRepository(td + "/data", model_guide=guide)
        repo.add_sample("ames")
        task = repo.create_model_task("ames.csv", "SalePrice")
        print("teaching:", task["teaching_note"])
        print("split:", task["split_note"])
        print("proposed:", [f["name"] for f in task["proposed"]])
    print("cassette entries:", len(json.loads(CASSETTE.read_text())))


if __name__ == "__main__":
    main()
