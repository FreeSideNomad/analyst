"""Saved charts domain — feature 014 (pure, no I/O).

A saved chart is a saved QUESTION, not a picture: the validated SQL that
answered it plus the chart configuration. Opening one re-runs the SQL
against current data — never a stale snapshot. The trust trail travels with
the chart (assumptions + lineage captured at save time; the SQL is live).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


class UnknownChartError(KeyError):
    """Acting on a saved chart that does not exist (stale UI, retry)."""


class ChartDataGoneError(RuntimeError):
    """A saved chart's underlying dataset no longer exists — the chart
    reports it clearly and stays deletable; it never crashes the app."""


def chart_id_for(name: str, taken: set[str]) -> str:
    """Stable human-readable id: a slug of the name, counter on collision."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "chart"
    if slug not in taken:
        return slug
    n = 2
    while f"{slug}-{n}" in taken:
        n += 1
    return f"{slug}-{n}"


@dataclass(frozen=True)
class SavedChart:
    """One kept answer: question + validated SQL + presentation."""

    chart_id: str
    name: str
    question: str
    sql: str
    chart_type: str  # "bar" | "line" | "stat" | "table" (presentation hint)
    title: str
    datasets: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    lineage: tuple[str, ...] = ()
    extras: dict = field(default_factory=dict)
