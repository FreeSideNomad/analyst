"""QueryPlanner — plans NL questions against the semantic catalog (feature 003).

One prompt-driven call per question, THROUGH the LLMGateway: the workspace
metadata (schema + profiles + catalog descriptions + capped samples) is
flattened into a CatalogPayload whose columns are named ``table.column``, so
the gateway's sample cap and egress log apply unchanged. SQL never executes
here — the planner only decides answer/clarify/abstain and proposes SQL that
the caller validates and runs locally in DuckDB.

Confidence gating (FR-11): the model is told to clarify when ambiguous and
abstain when out-of-scope; on top of that, an "answer" below MIN_CONFIDENCE is
demoted to an abstention with disclosure — the planner never presents a
low-confidence guess as an answer.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence

from pydantic import BaseModel, ValidationError

from analyst.agentic.gateway import LLMGateway
from analyst.domain.catalog import CatalogPayload, Clarification, ColumnMetadata
from analyst.domain.query import PlanAction, QueryPlan, QueryTable

MIN_CONFIDENCE = 0.5

PLANNER_SYSTEM_PROMPT = (
    "You are a careful data analyst planning a DuckDB SQL query over a small "
    "workspace of datasets. You are given the workspace metadata (tables, "
    "columns with types, null rates, distinct counts, a few sample values, "
    "and catalog descriptions when available) and a user question.\n"
    "Decide ONE of three actions:\n"
    '- "answer": the question is unambiguous and answerable from these '
    "tables. Produce a single DuckDB SELECT statement using ONLY the listed "
    "table and column names (never invent columns). Prefer simple aggregates; "
    "always alias computed columns.\n"
    '- "clarify": the question is ambiguous (e.g. several candidate columns '
    "or metrics could be meant). Do NOT guess — ask ONE question with 2-4 "
    "concrete options, each option starting with the exact column or choice "
    "it refers to, optionally followed by ' — ' and a short description.\n"
    '- "abstain": the question cannot be answered from these tables '
    "(out-of-scope, or would require data that is not present). Never "
    "fabricate.\n"
    "Also report your confidence (0.0-1.0), the assumptions you made, and the "
    "lineage (which tables and columns you used).\n"
    "Respond with ONLY a JSON object, no prose, of the exact shape:\n"
    '{"action": "answer"|"clarify"|"abstain", "confidence": number, '
    '"sql": string|null, "title": string|null, '
    '"assumptions": [string], "lineage": [string], '
    '"clarification": {"question": string, "options": [string], '
    '"column": string|null}|null, "reason": string|null}'
)


class _ClarificationOut(BaseModel):
    question: str
    options: list[str]
    column: str | None = None


class _PlanOut(BaseModel):
    action: str
    confidence: float = 0.0
    sql: str | None = None
    title: str | None = None
    assumptions: list[str] = []
    lineage: list[str] = []
    clarification: _ClarificationOut | None = None
    reason: str | None = None


def _extract_json(text: str) -> str:
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fenced:
        return fenced.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


def _flatten(tables: Sequence[QueryTable]) -> CatalogPayload:
    """Workspace metadata as one CatalogPayload (columns named table.column),
    so the gateway's governance (sample cap + egress log) applies unchanged."""
    columns = tuple(
        ColumnMetadata(
            name=f"{table.name}.{col.name}",
            inferred_type=col.inferred_type,
            null_rate=col.null_rate,
            distinct_count=col.distinct_count,
            samples=col.samples,
        )
        for table in tables
        for col in table.columns
    )
    return CatalogPayload(
        dataset="workspace",
        row_count=sum(t.row_count for t in tables),
        columns=columns,
    )


def render_plan_prompt(
    question: str, capped: CatalogPayload, tables: Sequence[QueryTable]
) -> str:
    """Deterministic prompt: sorted tables, profile-ordered columns, and the
    CAPPED samples from the gateway payload (descriptions are metadata)."""
    capped_samples = {c.name: c.samples for c in capped.columns}
    lines = [f"Question: {question}", "", "Workspace tables:"]
    for table in tables:
        suffix = f" — {table.description}" if table.description else ""
        lines.append(f"Table: {table.name} ({table.row_count} rows){suffix}")
        for col in table.columns:
            samples = ", ".join(
                str(s) for s in capped_samples.get(f"{table.name}.{col.name}", ())
            )
            described = f" — {col.description}" if col.description else ""
            lines.append(
                f"- {col.name} (type={col.inferred_type.value}, "
                f"null_rate={col.null_rate:.2f}, distinct={col.distinct_count}) "
                f"samples: [{samples}]{described}"
            )
    return "\n".join(lines)


def _abstain(reason: str) -> QueryPlan:
    return QueryPlan(action=PlanAction.ABSTAIN, reason=reason)


def _to_plan(parsed: _PlanOut) -> QueryPlan:
    try:
        action = PlanAction(parsed.action)
    except ValueError:
        return _abstain(f"The planner chose an unknown action '{parsed.action}'.")

    if action is PlanAction.CLARIFY:
        if parsed.clarification is None or len(parsed.clarification.options) < 2:
            return _abstain("The planner clarified without usable options.")
        return QueryPlan(
            action=action,
            confidence=parsed.confidence,
            clarification=Clarification(
                question=parsed.clarification.question,
                options=tuple(parsed.clarification.options),
                column=parsed.clarification.column,
            ),
        )
    if action is PlanAction.ABSTAIN:
        return QueryPlan(
            action=action,
            confidence=parsed.confidence,
            reason=parsed.reason or "The question is outside the loaded datasets.",
        )
    # answer
    if not parsed.sql or not parsed.sql.strip():
        return _abstain("The planner answered without SQL.")
    if parsed.confidence < MIN_CONFIDENCE:
        return _abstain(
            f"Planning confidence ({parsed.confidence:.2f}) is too low to "
            "present an answer."
        )
    return QueryPlan(
        action=action,
        confidence=parsed.confidence,
        sql=parsed.sql.strip(),
        title=parsed.title,
        assumptions=tuple(parsed.assumptions),
        lineage=tuple(parsed.lineage),
    )


class QueryPlanner:
    """Plans one question per gateway call; parsing failures abstain."""

    def __init__(self, gateway: LLMGateway):
        self.gateway = gateway

    def plan(self, question: str, tables: Sequence[QueryTable]) -> QueryPlan:
        ordered = tuple(sorted(tables, key=lambda t: t.name))
        raw = self.gateway.run(
            _flatten(ordered),
            PLANNER_SYSTEM_PROMPT,
            lambda capped: render_plan_prompt(question, capped, ordered),
        )
        try:
            parsed = _PlanOut.model_validate_json(_extract_json(raw))
        except ValidationError, json.JSONDecodeError:
            return _abstain("The planning response could not be parsed.")
        return _to_plan(parsed)

    def replan(
        self,
        question: str,
        tables: Sequence[QueryTable],
        asked: Clarification,
        choice: str,
    ) -> QueryPlan:
        """Re-plan after the user answered a clarification."""
        augmented = (
            f"{question}\n\n"
            f"You previously asked: {asked.question}\n"
            f"The user chose: {choice}\n"
            "Plan the answer using that choice; do not ask again."
        )
        return self.plan(augmented, tables)
