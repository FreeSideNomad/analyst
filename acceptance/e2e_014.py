"""Step handlers for feature 014 — charts & data exports.

Chart-lifecycle and export scenarios bind over the in-process seam (real
StoreRepository + chart service in the scenario tmp_path; restarts rebuild
the stack). The two workbench flows bind to Playwright against the fixtures
app. Deterministic — reopening a chart executes its stored query; no model
calls anywhere.

Bindings land slice by slice during implementation (CP5); unbound steps fail
the board explicitly with NOT YET IMPLEMENTED — the intended red.
"""

from __future__ import annotations

from acceptance.e2e_base import (
    ScenarioContext,
    _e2e_fresh,
    _e2e_stack,
    expect_,
    make_registry,
)

step, run_step = make_registry()
_expect = expect_

__all__ = ["ScenarioContext", "run_step", "_e2e_stack", "_e2e_fresh"]
