"""Model guidance — feature 012 (agentic layer).

The model NEVER writes training code. Its entire authority is this output
schema: a teaching note, a split note, and a feature proposal (name +
plain-language reason per feature) drawn from the dataset's columns — the
committed trainer (engine/mltrain.py) does everything else. It sees only
planner-style metadata (schema, profile facts, catalog text; never rows),
through the same governed gateway, cassette-recordable for the board.
"""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, ValidationError

from analyst.agentic.gateway import LLMGateway
from analyst.agentic.planner import _flatten
from analyst.domain.query import QueryTable

SYSTEM_PROMPT = (
    "You are guiding a person who understands basic concepts but writes no "
    "code through defining a prediction model on ONE table. Respond with "
    "JSON only:\n"
    '{"teaching_note": str, "split_note": str, '
    '"features": [{"name": str, "reason": str}]}\n'
    "Rules: teaching_note explains, in two friendly sentences anchored to "
    "basic linear regression, what predicting this target means for this "
    "data. split_note explains holding out a fifth of the rows as an "
    "honesty test, phrased as a decision the person is making. Propose 10 "
    "to 18 features by EXACT column name from the listed columns — never "
    "the target itself, never identifier-like columns — each with a one-"
    "sentence plain-language reason tied to what the column means. Prefer "
    "columns whose meaning the catalog explains."
)


class ModelGuidanceError(RuntimeError):
    """Guidance could not be produced or parsed; nothing was created."""


class FeatureProposal(BaseModel):
    name: str
    reason: str


class GuidanceResult(BaseModel):
    teaching_note: str
    split_note: str
    features: list[FeatureProposal]


def render_guidance_prompt(table: QueryTable, target: str) -> str:
    lines = [
        f'Table "{table.name}" ({table.row_count} rows): {table.description}',
        f"Target to predict: {target}",
        "Columns:",
    ]
    for column in table.columns:
        samples = ", ".join(str(s) for s in column.samples[:4])
        lines.append(
            f"- {column.name} ({column.inferred_type.value}, "
            f"{column.distinct_count} distinct"
            f"{', ' + column.description if column.description else ''})"
            f"{' e.g. ' + samples if samples else ''}"
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


class ModelGuide:
    def __init__(self, gateway: LLMGateway):
        self.gateway = gateway

    def guide(self, table: QueryTable, target: str) -> GuidanceResult:
        try:
            raw = self.gateway.run(
                _flatten((table,)),
                SYSTEM_PROMPT,
                lambda _capped: render_guidance_prompt(table, target),
            )
        except Exception as exc:  # noqa: BLE001 - ANY failure ends plainly
            raise ModelGuidanceError(
                f"The guidance could not be produced ({exc}). Nothing was "
                "created — please try again."
            ) from exc
        try:
            result = GuidanceResult.model_validate_json(_extract_json(raw))
        except (ValidationError, json.JSONDecodeError) as exc:
            raise ModelGuidanceError(
                f"The guidance response could not be parsed: {exc}"
            ) from exc
        # Defense in depth: the target never enters the proposal.
        result.features = [f for f in result.features if f.name != target]
        return result
