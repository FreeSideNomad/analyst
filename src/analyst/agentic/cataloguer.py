"""Cataloguer — turns dataset metadata into an agent-authored catalog entry.

Sends schema + profiles + capped samples (via the LLMGateway), gets back a
plain-English table/column description + roles, and (AC-22) a structured
clarification when the model cannot confidently describe a column.
"""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, ValidationError

from analyst.agentic.gateway import LLMGateway
from analyst.domain.catalog import (
    CatalogEntry,
    CatalogPayload,
    Clarification,
    ColumnDescription,
)


class CatalogingError(RuntimeError):
    """Raised when the model's cataloguing response cannot be used (AC-17)."""


SYSTEM_PROMPT = (
    "You are a data cataloguer. Given a dataset's schema, per-column profiles, "
    "and a few sample values, write a concise plain-English description of the "
    "table and of each column, and infer each column's domain role "
    "(one of: identifier, measure, category, timestamp, text, other). "
    "When a column's meaning is genuinely unclear from its name, type, and "
    "samples, add a clarification: a question plus 2-4 concrete options. "
    "Respond with ONLY a JSON object, no prose, of the exact shape:\n"
    '{"table_description": str, '
    '"columns": [{"name": str, "description": str, "role": str}], '
    '"clarifications": [{"column": str, "question": str, "options": [str]}]}'
)


class _ColumnOut(BaseModel):
    name: str
    description: str
    role: str


class _ClarificationOut(BaseModel):
    question: str
    options: list[str]
    column: str | None = None


class _CatalogOut(BaseModel):
    table_description: str
    columns: list[_ColumnOut]
    clarifications: list[_ClarificationOut] = []


def render_prompt(payload: CatalogPayload) -> str:
    lines = [
        f"Dataset: {payload.dataset}",
        f"Row count: {payload.row_count}",
        "Columns:",
    ]
    for col in payload.columns:
        samples = ", ".join(str(s) for s in col.samples)
        lines.append(
            f"- {col.name} (type={col.inferred_type.value}, "
            f"null_rate={col.null_rate:.2f}, distinct={col.distinct_count}) "
            f"samples: [{samples}]"
        )
    return "\n".join(lines)


def _extract_json(text: str) -> str:
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fenced:
        return fenced.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


class Cataloguer:
    def __init__(self, gateway: LLMGateway):
        self.gateway = gateway

    def catalog(self, payload: CatalogPayload) -> CatalogEntry:
        raw = self.gateway.run(payload, SYSTEM_PROMPT, render_prompt)
        try:
            parsed = _CatalogOut.model_validate_json(_extract_json(raw))
        except (ValidationError, json.JSONDecodeError) as exc:
            raise CatalogingError(
                f"The cataloguing response could not be parsed: {exc}"
            ) from exc
        return CatalogEntry(
            table_description=parsed.table_description,
            columns=tuple(
                ColumnDescription(name=c.name, description=c.description, role=c.role)
                for c in parsed.columns
            ),
            clarifications=tuple(
                Clarification(
                    question=c.question,
                    options=tuple(c.options),
                    column=c.column,
                )
                for c in parsed.clarifications
            ),
        )
