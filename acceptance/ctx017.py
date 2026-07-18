"""Step handlers for feature 017 — cross-database joins.

In-process seam: two synthetic SQLite databases connected through the real
DatabaseManager; the NL turn replays tests/cassettes/cross_db_planner.json.
No browser (the workbench surface is untouched by this feature).
"""

from __future__ import annotations


from acceptance.e2e_base import ScenarioContext, make_registry

step, run_step = make_registry()

__all__ = ["ScenarioContext", "run_step"]
