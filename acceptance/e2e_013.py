"""Step handlers for feature 013 — data normalization detection.

Detection/apply/revoke scenarios bind over the in-process seam (a real
DatasetStore + repository in the scenario tmp_path); the workbench flow binds
to Playwright against the fixtures app (a seeded proposal on the sample sales
table). Deterministic — detection is local, no model calls.

Bindings land slice by slice during implementation (CP5); unbound steps fail
the board explicitly with NOT YET IMPLEMENTED, which is the intended red.
"""

from __future__ import annotations

from acceptance.e2e_base import ScenarioContext, make_registry

step, run_step = make_registry()

__all__ = ["ScenarioContext", "run_step"]
