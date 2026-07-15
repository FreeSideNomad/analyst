"""Saved-chart routes — feature 014.

A saved chart is a saved question + validated SQL + presentation config;
GET /charts/{id} RE-RUNS the query against current data (never a snapshot).
Exports stream engine-generated files; nothing here ever calls a model.
"""

from __future__ import annotations

import tempfile

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from analyst.api.deps import get_repository
from analyst.api.repository import DatasetRepository
from analyst.api.schemas import Camel
from analyst.domain.charts import ChartDataGoneError, UnknownChartError

router = APIRouter(prefix="/api")

_MEDIA = {
    "csv": "text/csv",
    "parquet": "application/vnd.apache.parquet",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


class SaveChartRequest(Camel):
    name: str
    question: str = ""
    sql: str
    chart_type: str = "bar"
    title: str = ""
    datasets: list[str] = []
    assumptions: list[str] = []
    lineage: list[str] = []


class RenameChartRequest(Camel):
    name: str


class SavedChartSchema(Camel):
    chart_id: str
    name: str
    question: str
    chart_type: str
    title: str
    datasets: list[str] = []

    @classmethod
    def from_domain(cls, chart) -> "SavedChartSchema":  # noqa: ANN001
        return cls(
            chart_id=chart.chart_id,
            name=chart.name,
            question=chart.question,
            chart_type=chart.chart_type,
            title=chart.title,
            datasets=list(chart.datasets),
        )


def _require_chart(call, chart_id: str):  # noqa: ANN001, ANN202
    try:
        return call()
    except UnknownChartError:
        raise HTTPException(404, f"Saved chart '{chart_id}' not found") from None
    except ChartDataGoneError as exc:
        raise HTTPException(409, str(exc)) from None


@router.get("/charts")
def list_charts(repo: DatasetRepository = Depends(get_repository)) -> dict:
    return {"charts": [SavedChartSchema.from_domain(c).dump() for c in repo.charts()]}


@router.post("/charts")
def save_chart(
    body: SaveChartRequest, repo: DatasetRepository = Depends(get_repository)
) -> dict:
    try:
        chart = repo.save_chart(
            name=body.name,
            question=body.question,
            sql=body.sql,
            chart_type=body.chart_type,
            title=body.title or body.name,
            datasets=body.datasets,
            assumptions=body.assumptions,
            lineage=body.lineage,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    return SavedChartSchema.from_domain(chart).dump()


@router.get("/charts/{chart_id}")
def open_chart(
    chart_id: str, repo: DatasetRepository = Depends(get_repository)
) -> dict:
    answer = _require_chart(lambda: repo.open_chart(chart_id), chart_id)
    return answer.dump()


@router.patch("/charts/{chart_id}")
def rename_chart(
    chart_id: str,
    body: RenameChartRequest,
    repo: DatasetRepository = Depends(get_repository),
) -> dict:
    _require_chart(lambda: repo.rename_chart(chart_id, body.name), chart_id)
    return {"chartId": chart_id, "name": body.name}


@router.delete("/charts/{chart_id}", status_code=204)
def delete_chart(
    chart_id: str, repo: DatasetRepository = Depends(get_repository)
) -> None:
    _require_chart(lambda: repo.delete_chart(chart_id), chart_id)


@router.get("/charts/{chart_id}/export")
def export_chart(
    chart_id: str,
    format: str = "csv",
    repo: DatasetRepository = Depends(get_repository),
) -> FileResponse:
    from analyst.engine.exports import FORMATS, export_query

    if format not in FORMATS:
        raise HTTPException(400, f"Unsupported export format '{format}'")
    chart = next((c for c in repo.charts() if c.chart_id == chart_id), None)
    if chart is None:
        raise HTTPException(404, f"Saved chart '{chart_id}' not found")
    store = getattr(repo, "store", None)
    if store is None:
        raise HTTPException(400, "Exports need the real data store")
    path = tempfile.NamedTemporaryFile(suffix=f".{format}", delete=False).name
    _require_chart(lambda: export_query(store, chart.sql, format, path), chart_id)
    return FileResponse(
        path,
        media_type=_MEDIA[format],
        filename=f"{chart.chart_id}.{format}",
        content_disposition_type="attachment",
    )
