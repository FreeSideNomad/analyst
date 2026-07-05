"""Step handlers for feature 009 — semantic depth (PK/FK discovery + richer
catalog to UI & planner).

Scaffold only (Checkpoint 3): the registry + shared fixtures are wired, but no
steps are bound yet — so the generated board is RED by construction (every step
fails with NOT YET IMPLEMENTED). Bindings are added slice by slice in CP5.

Built on acceptance/e2e_base.py (fixtures API + production frontend build +
Chromium), like features 002/003/005/006. Backend discovery/validation
scenarios will bind over the in-process seam + HTTP against a real-store
service; focus + async-progress flows bind to Playwright.
"""

from __future__ import annotations

from typing import Any

from acceptance.e2e_base import (  # noqa: F401 (re-exported for the generated board)
    REPO_ROOT,
    ScenarioContext,
    _e2e_fresh,
    _e2e_stack,
    expect_,
    make_registry,
)

CHINOOK = REPO_ROOT / "tests" / "golden" / "chinook.sqlite"

step, run_step = make_registry()
_expect = expect_

__all__ = [
    "ScenarioContext",
    "run_step",
    "_e2e_stack",
    "_e2e_fresh",
]

_REAL: dict[str, Any] = {}

# --------------------------------------------------------------------------- #
# No step bindings yet — CP5 adds them one slice at a time. Until then every
# scenario fails explicitly with "NOT YET IMPLEMENTED: <step>" (the red board
# that drives the next slice).
# --------------------------------------------------------------------------- #
