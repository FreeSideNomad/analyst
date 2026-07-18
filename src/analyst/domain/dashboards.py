"""Dashboards domain — feature 015 (pure, no I/O).

A dashboard is a named grid of widgets. A widget IS a saved-chart shape —
question + validated SQL + presentation + trust-trail material — plus its
source dataset (drill-down target). Filters are declared dimensions; their
application happens in the engine, before aggregation, never here.
"""

from __future__ import annotations

from dataclasses import dataclass, field


class UnknownDashboardError(KeyError):
    """Acting on a dashboard (or widget) that does not exist."""


@dataclass(frozen=True)
class DashboardWidget:
    widget_id: str
    question: str
    sql: str  # must carry the /*FILTERS*/ marker (engine-validated)
    chart_type: str
    title: str
    source: str  # underlying dataset name (drill-down + filter applicability)
    assumptions: tuple[str, ...] = ()
    lineage: tuple[str, ...] = ()


@dataclass(frozen=True)
class DashboardFilter:
    column: str
    label: str


@dataclass(frozen=True)
class Dashboard:
    dashboard_id: str
    name: str
    widgets: tuple[DashboardWidget, ...] = ()
    filters: tuple[DashboardFilter, ...] = field(default_factory=tuple)
