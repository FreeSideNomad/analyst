"""Curation synthesis — feature 016 (agentic layer).

A person has settled a question of meaning (a clarification answer or a
suggested correction); their input is GROUND TRUTH. The model completes the
semantic analysis by rewriting AT MOST two things — the affected column's
description and its own table's description — a blast radius enforced by
the output schema itself (AC-4), not by convention.

Speaks through LLMGateway: metadata-only egress (profile facts + current
catalog text + the user's words; never data rows), record/replay-able for a
deterministic acceptance board. Prompt and output schema are versioned
artifacts (charter).
"""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, ValidationError

from analyst.domain.catalog import CatalogPayload
from analyst.agentic.gateway import LLMGateway

SYSTEM_PROMPT = (
    "You complete the semantic analysis of one column of tabular data for a "
    "data catalog. A person has settled a question about its meaning; treat "
    "their answer as ground truth, reconciled with the profile evidence. "
    "Rewrite the column's description, and the table's description ONLY if "
    "it depended on the settled meaning. Keep the catalog's concise, factual "
    "voice (one to two sentences each). Respond with JSON only: "
    '{"column_description": string or null, "table_description": string or '
    "null}. Use null for anything you leave unchanged."
)


class CurationError(RuntimeError):
    """The completion could not be produced or parsed; nothing was changed."""


class CurationResult(BaseModel):
    column_description: str | None = None
    table_description: str | None = None


def render_curation_prompt(
    capped: CatalogPayload,
    column: str | None,
    question: str | None,
    user_input: str,
    current_column_description: str,
    current_table_description: str,
) -> str:
    lines = [f"Table: {capped.dataset} ({capped.row_count} rows)"]
    lines.append(f"Current table description: {current_table_description or '(none)'}")
    if column:
        meta = next((c for c in capped.columns if c.name == column), None)
        lines.append(f"Column under curation: {column}")
        lines.append(
            f"Current column description: {current_column_description or '(none)'}"
        )
        if meta is not None:
            samples = ", ".join(str(s) for s in meta.samples)
            lines.append(
                f"Profile: type={meta.inferred_type.value}, "
                f"distinct={meta.distinct_count}, null_rate={meta.null_rate:.2f}, "
                f"sample values: {samples}"
            )
    else:
        lines.append("The TABLE description itself is under curation.")
    if question:
        lines.append(f"Open question being answered: {question}")
    lines.append(f"The person's settled answer (ground truth): {user_input}")
    return "\n".join(lines)


def _extract_json(text: str) -> str:
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fenced:
        return fenced.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


class Curator:
    """Completes a curation through the gateway; blast radius = the schema."""

    def __init__(self, gateway: LLMGateway):
        self.gateway = gateway

    def complete(
        self,
        payload: CatalogPayload,
        column: str | None,
        question: str | None,
        user_input: str,
        current_column_description: str = "",
        current_table_description: str = "",
    ) -> CurationResult:
        try:
            raw = self.gateway.run(
                payload,
                SYSTEM_PROMPT,
                lambda capped: render_curation_prompt(
                    capped,
                    column,
                    question,
                    user_input,
                    current_column_description,
                    current_table_description,
                ),
            )
        except Exception as exc:  # noqa: BLE001 - ANY failure ends plainly
            raise CurationError(
                f"The semantic analysis could not be completed ({exc}). "
                "Nothing was changed — please try again."
            ) from exc
        try:
            return CurationResult.model_validate_json(_extract_json(raw))
        except (ValidationError, json.JSONDecodeError) as exc:
            raise CurationError(
                f"The curation response could not be parsed: {exc}"
            ) from exc
