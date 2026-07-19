"""Step handlers for feature 019 — guided graph authoring.

The curated Berka corpus arrives the two ways a real user's data arrives
(seeded demo Postgres; file uploads) and the generated authoring flow must
reproduce the shipped 018 curated reference. Agent authoring turns replay
tests/cassettes/graph_authoring.json. Container scenario: analyst:ml with
the demo database alongside — the owner's autonomy gate.

Bindings land per slice; unbound steps fail NOT YET IMPLEMENTED.
"""

from __future__ import annotations

import os

os.environ.setdefault("ANALYST_ML_CACHE", "tests/.ml_cache")

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
