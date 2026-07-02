"""HTTP API layer for analyst — FastAPI over the feature-001 domain.

Serializes the frozen domain dataclasses (analyst.domain.*) to a camelCase
wire contract, and serves either in-memory fixtures (dev) or the real
DuckDB-backed store (prod). See CONTRACT.md for the full spec.
"""

from __future__ import annotations

from analyst.api.app import app, create_app

__all__ = ["app", "create_app"]
