"""Step handlers for feature 015 — interactive dashboards.

Assembly/edit replay the dashboards cassette; viewing/filtering scenarios
run fully offline over the in-process seam; workbench flows bind to
Playwright against the fixtures app. Bindings land per slice; unbound
steps fail NOT YET IMPLEMENTED — the intended red.
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
_ = _STACK  # keep the import: browser steps use it and ruff must not strip it

__all__ = ["ScenarioContext", "run_step", "_e2e_stack", "_e2e_fresh"]
