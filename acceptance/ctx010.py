"""Step handlers for feature 010 — workspace-aware cataloguing.

All scenarios bind over the in-process seam: a real DatasetStore +
IngestionService per scenario in the pytest tmp_path. Cataloguing context /
retroactive / persistence assertions read the real CatalogEntry objects and
sidecars — no browser, no live model calls (the LLM-path scenario replays a
cassette; the offline path is deterministic by construction).

Binding status: intentionally unbound — the red board drives the slices.
As each slice lands, add its step bindings here and re-run the pipeline.
"""

from __future__ import annotations

from acceptance.e2e_base import ScenarioContext, make_registry

step, run_step = make_registry()

__all__ = ["ScenarioContext", "run_step"]
