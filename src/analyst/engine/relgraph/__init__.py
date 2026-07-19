"""Relational-graph (GNN) engine — feature 018. FIXED, COMMITTED CODE.

Vendored from the owner's paper repo (~/code/relational-graph, same author)
and adapted to live inside analyst: datasets ship as package data, the
cache roots under ANALYST_ML_CACHE, and the paper's CLI/report layers are
dropped. The port stays faithful — same architecture, hyperparameters,
split policy, and seeding — because reproducing the paper's RESULTS.md
numbers on Berka is this feature's code-validity gate.

Heavy imports (torch, torch_geometric, relbench, torch_frame) happen
lazily inside functions; `available()` is the cheap probe the lean image
uses to answer honestly that the ML variant is needed.
"""

from __future__ import annotations

import importlib.util


def available() -> bool:
    """True when the optional `ml` extra (torch stack) is installed."""
    return all(
        importlib.util.find_spec(mod) is not None
        for mod in ("torch", "torch_geometric", "relbench", "torch_frame", "yaml")
    )
