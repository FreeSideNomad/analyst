"""Dashboard routes — feature 015.

Assembly/edit go through the agent (502 when unavailable/failed, catalog of
dashboards untouched); run/drill execute stored, re-guarded SQL only —
viewing needs no model. Widgets fail alone: /run returns per-widget results.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from analyst.api.deps import get_repository
from analyst.api.repository import DatasetRepository
from analyst.api.schemas import Camel
from analyst.domain.dashboards import UnknownDashboardError

router = APIRouter(prefix="/api")


class DashboardRequest(Camel):
    request: str


class RunRequest(Camel):
    filters: list[dict] = []


class DrillRequest(Camel):
    widget_id: str
    filters: list[dict] = []


def _meta(dashboard) -> dict:  # noqa: ANN001
    return {
        "dashboardId": dashboard.dashboard_id,
        "name": dashboard.name,
        "filters": [{"column": f.column, "label": f.label} for f in dashboard.filters],
        "widgets": [
            {
                "widgetId": w.widget_id,
                "question": w.question,
                "title": w.title,
                "chartType": w.chart_type,
                "source": w.source,
            }
            for w in dashboard.widgets
        ],
    }


def _pairs(filters: list[dict]) -> list[tuple[str, str]]:
    return [(f["column"], str(f["value"])) for f in filters]


def _guard(call):  # noqa: ANN001, ANN202
    from analyst.agentic.dashboards import DashboardAssemblyError

    try:
        return call()
    except UnknownDashboardError as exc:
        raise HTTPException(404, f"No such dashboard or widget: {exc}") from None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    except DashboardAssemblyError as exc:
        raise HTTPException(502, str(exc)) from None


@router.get("/dashboards")
def list_dashboards(repo: DatasetRepository = Depends(get_repository)) -> dict:
    return {"dashboards": [_meta(d) for d in repo.dashboards()]}


@router.post("/dashboards")
def create_dashboard(
    body: DashboardRequest, repo: DatasetRepository = Depends(get_repository)
) -> dict:
    out = _guard(lambda: repo.create_dashboard(body.request))
    if out["clarification"] is not None:
        c = out["clarification"]
        return {"clarification": {"question": c.question, "options": c.options}}
    return {"dashboard": _meta(out["dashboard"]), "clarification": None}


@router.post("/dashboards/{dashboard_id}/edit")
def edit_dashboard(
    dashboard_id: str,
    body: DashboardRequest,
    repo: DatasetRepository = Depends(get_repository),
) -> dict:
    out = _guard(lambda: repo.edit_dashboard(dashboard_id, body.request))
    if out["clarification"] is not None:
        c = out["clarification"]
        return {"clarification": {"question": c.question, "options": c.options}}
    return {"dashboard": _meta(out["dashboard"]), "clarification": None}


@router.post("/dashboards/{dashboard_id}/run")
def run_dashboard(
    dashboard_id: str,
    body: RunRequest,
    repo: DatasetRepository = Depends(get_repository),
) -> dict:
    out = _guard(lambda: repo.run_dashboard(dashboard_id, _pairs(body.filters)))
    return {
        "dashboard": _meta(out["dashboard"]),
        "widgets": {
            wid: {
                "answer": entry["answer"].dump() if entry["answer"] else None,
                "error": entry["error"],
                "unaffectedBy": entry["unaffected_by"],
            }
            for wid, entry in out["widgets"].items()
        },
    }


@router.post("/dashboards/{dashboard_id}/drill")
def drill_dashboard(
    dashboard_id: str,
    body: DrillRequest,
    repo: DatasetRepository = Depends(get_repository),
) -> dict:
    answer = _guard(
        lambda: repo.drill_dashboard(dashboard_id, body.widget_id, _pairs(body.filters))
    )
    return answer.dump()


@router.delete("/dashboards/{dashboard_id}", status_code=204)
def delete_dashboard(
    dashboard_id: str, repo: DatasetRepository = Depends(get_repository)
) -> None:
    _guard(lambda: repo.delete_dashboard(dashboard_id))


@router.delete("/dashboards/{dashboard_id}/widgets/{widget_id}", status_code=204)
def remove_widget(
    dashboard_id: str,
    widget_id: str,
    repo: DatasetRepository = Depends(get_repository),
) -> None:
    _guard(lambda: repo.remove_widget(dashboard_id, widget_id))
