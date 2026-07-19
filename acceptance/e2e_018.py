"""Step handlers for feature 018 — relational graph (GNN) models.

Reference-data scenarios run against the REAL Berka dataset (PKDD'99),
downloaded on demand from public mirrors into tests/.ml_cache/ (gitignored)
— each tier is validated against ITS OWN number from the owner's paper
(RESULTS.md), within ±0.03, deterministic seeds. The heavy three-task
matrix runs with ML_FULL=1 (nightly / pre-ship); the fast board covers
loan_default end to end. The container scenario builds and boots the
analyst:ml image variant — the owner's autonomy gate.

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
