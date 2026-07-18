"""Step handlers for feature 016 — catalog curation.

Curation scenarios bind over the in-process seam (StoreRepository in the
scenario tmp_path); agent synthesis replays the curation cassette so the
board is deterministic and offline. Workbench flows bind to Playwright
against the fixtures app. Bindings land per slice; unbound steps fail
NOT YET IMPLEMENTED — the intended red.
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
