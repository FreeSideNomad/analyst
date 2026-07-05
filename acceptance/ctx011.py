"""Step handlers for feature 011 — encrypted-at-rest credentials.

Scenarios bind over the in-process seam: a workspace repository + database
manager over the pytest tmp_path, connecting a synthetic SQLite database
whose ConnectionSpec carries a username/password (unused by SQLite but sealed
and persisted like any credential, so the secret's whole lifecycle is
observable offline). "The service restarts" rebuilds the workspace stack over
the same data directory. The read-only-guidance scenario binds to the shipped
connect form's content. No browser, no live model calls.

Binding status: intentionally unbound — the red board drives the slices.
"""

from __future__ import annotations

from acceptance.e2e_base import ScenarioContext, make_registry

step, run_step = make_registry()

__all__ = ["ScenarioContext", "run_step"]
