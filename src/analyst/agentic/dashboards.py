"""Dashboard assembly — feature 015 (agentic layer).

The model turns a plain-English request (plus, when editing, the current
dashboard spec) into a STRUCTURED dashboard spec: 2–4 widgets (question +
SELECT-only SQL carrying the ``WHERE /*FILTERS*/ 1=1`` marker + chart type +
source table) and the filterable dimensions — or a clarification when the
request is under-specified (AskQuestion, charter). It sees exactly what the
Q&A planner sees: capped, metadata-only table summaries through the same
gateway (governance). Every widget SQL is re-validated by the caller; a
malformed spec is rejected WHOLE.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence

from pydantic import BaseModel, ValidationError

from analyst.agentic.gateway import LLMGateway
from analyst.agentic.planner import _flatten
from analyst.domain.query import QueryTable

SYSTEM_PROMPT = (
    "You assemble analytical dashboards over the user's local tables. "
    "Respond with JSON only. Either a dashboard spec:\n"
    '{"name": str, "widgets": [{"question": str, "sql": str, '
    '"chart_type": "bar"|"line"|"stat", "title": str, "source": str}], '
    '"filters": [{"column": str, "label": str}]}\n'
    'or, when the request is too vague to build well: {"clarification": '
    '{"question": str, "options": [str, ...]}}.\n'
    "Rules: 2 to 4 widgets; SQL is SELECT-only over the listed tables, "
    'quoting table names exactly as given (e.g. FROM "sales.csv"); EVERY '
    "widget SQL must contain the literal marker inside its WHERE clause: "
    "WHERE /*FILTERS*/ 1=1 (before any GROUP BY) so dashboard filters can "
    "re-scope it; source names the single table the widget reads; filters "
    "list only real columns shared by at least one widget's source; keep "
    "titles short and business-phrased. When the request does not make clear "
    "which subject or tables it concerns — it could equally target several "
    "unrelated tables — respond with the clarification form instead of "
    "guessing. When the request names multiple subjects (e.g. sales AND "
    "staffing), cover each with at least one widget."
)


class DashboardAssemblyError(RuntimeError):
    """The assembly could not be produced or parsed; nothing was created."""


class WidgetSpec(BaseModel):
    question: str
    sql: str
    chart_type: str = "bar"
    title: str
    source: str


class FilterSpec(BaseModel):
    column: str
    label: str


class ClarificationSpec(BaseModel):
    question: str
    options: list[str]


class AssemblyResult(BaseModel):
    name: str | None = None
    widgets: list[WidgetSpec] = []
    filters: list[FilterSpec] = []
    clarification: ClarificationSpec | None = None


def render_assembly_prompt(
    request: str,
    tables: Sequence[QueryTable],
    current_spec: str | None,
) -> str:
    lines = ["Tables available (metadata only):"]
    for table in tables:
        lines.append(f'- "{table.name}" ({table.row_count} rows): {table.description}')
        for column in table.columns:
            samples = ", ".join(str(s) for s in column.samples[:4])
            lines.append(
                f"    {column.name} ({column.inferred_type.value}"
                f"{', ' + column.description if column.description else ''})"
                f"{' e.g. ' + samples if samples else ''}"
            )
    if current_spec:
        lines.append("Current dashboard spec (you are EDITING it):")
        lines.append(current_spec)
    lines.append(f"Request: {request}")
    return "\n".join(lines)


def _extract_json(text: str) -> str:
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fenced:
        return fenced.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


class DashboardAssembler:
    def __init__(self, gateway: LLMGateway):
        self.gateway = gateway

    def assemble(
        self,
        request: str,
        tables: Sequence[QueryTable],
        current_spec: str | None = None,
    ) -> AssemblyResult:
        ordered = tuple(sorted(tables, key=lambda t: t.name))
        try:
            raw = self.gateway.run(
                _flatten(ordered),
                SYSTEM_PROMPT,
                lambda _capped: render_assembly_prompt(request, ordered, current_spec),
            )
        except Exception as exc:  # noqa: BLE001 - ANY failure ends plainly
            raise DashboardAssemblyError(
                f"The dashboard could not be assembled ({exc}). "
                "Nothing was created — please try again."
            ) from exc
        try:
            return AssemblyResult.model_validate_json(_extract_json(raw))
        except (ValidationError, json.JSONDecodeError) as exc:
            raise DashboardAssemblyError(
                f"The dashboard assembly could not be parsed: {exc}"
            ) from exc
