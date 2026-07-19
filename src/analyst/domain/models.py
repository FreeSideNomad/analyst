"""Model-registry domain — feature 012 (pure)."""

from __future__ import annotations


class UnknownModelError(KeyError):
    """Acting on a model/task that does not exist."""
