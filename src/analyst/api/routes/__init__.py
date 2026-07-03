"""Per-area API routers.

Parallel-session ownership (see docs/PARALLEL_PLAN.md):
- datasets.py — feature 001/002 surface (stable)
- qa.py       — feature 003 (NL Q&A) owns this
- system.py   — health + test-only reset (stable)
- auth.py     — feature 004 adds this
- databases.py— feature 005 adds this
"""
