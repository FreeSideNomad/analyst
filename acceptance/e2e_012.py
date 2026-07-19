"""Step handlers for feature 012 — guided predictive models (MVP).

Realistic-data scenarios run against the REAL Ames dataset, downloaded on
demand into tests/.ml_cache/ (gitignored, like the golden corpus) — the
owner's directive: the acceptance loop iterates against real data until
green. Agent turns replay tests/cassettes/models_guidance.json. The
container scenario builds and boots the actual Docker image in replay mode
and drives it with Playwright (skippable with CONTAINER_E2E=0; on by
default — it is the owner's autonomy condition).

Bindings land per slice; unbound steps fail NOT YET IMPLEMENTED.
"""

from __future__ import annotations

from acceptance.e2e_base import (
    _STACK,
    ScenarioContext,
    _e2e_fresh,
    _e2e_stack,
    expect_,
    make_registry,
)

step, run_step = make_registry()
_expect = expect_
_ = _STACK  # browser steps use it; keep ruff from stripping the import

__all__ = ["ScenarioContext", "run_step", "_e2e_stack", "_e2e_fresh"]
