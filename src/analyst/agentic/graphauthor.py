"""Graph-task authoring — feature 019 (agentic layer).

The one bounded authoring turn: the user's question in their own words +
the DERIVED structure summary (tables, validated links, time candidates —
never rows) go in; a set of declarative decisions comes out. The LLM's
entire authority is this schema — it never writes training code, never
invents links, and the hidden-column set is NOT its call (computed
mechanically from the outcome definition; users can only grow it).
"""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, ValidationError

from analyst.agentic.gateway import LLMGateway
from analyst.agentic.planner import _flatten
from analyst.domain.query import QueryTable

SYSTEM_PROMPT = (
    "You are turning a person's plain-language prediction wish into "
    "concrete, honest decisions for a relational model. You see the "
    "derived structure of their linked tables (names, columns, validated "
    "links, date-column candidates) — never their data. Respond with "
    "JSON only:\n"
    '{"entity_table": str, "entity_column": str, "time_column": str, '
    '"horizon_days": int, "val_cutoff": "YYYY-MM-DD", '
    '"test_cutoff": "YYYY-MM-DD", "label_sql": str, '
    '"time_columns": {"<table>": str|null, ...}, '
    '"outcome_columns": [str, ...], '
    '"framing": {"question": str, "moment": str, "honesty": str}}\n'
    "Rules: entity_table/columns must come from the listed structure. "
    "label_sql is ONE SELECT over the listed tables returning the entity "
    "id column, an as_of date column, and a 0/1 label column — nothing "
    "else. Outcome columns it reads will be hidden from the model "
    "automatically. time_columns picks the EVENT-time column per table "
    "(null for tables whose dates are attributes, like birth dates). "
    "outcome_columns lists EVERY entity-table column that records the "
    "outcome or anything only knowable after the prediction moment — "
    "recorded statuses, running repayment totals, closure dates; they "
    "will be hidden from the model. "
    "Cutoffs must split the as_of range so train, validation and test "
    "are all non-empty, with test covering roughly the final year. "
    "framing explains the question, the prediction moment, and why the "
    "outcome columns are hidden — two friendly sentences each, no jargon."
)


class GraphAuthoringError(RuntimeError):
    """Authoring could not be produced or validated; nothing was created."""


class AuthoredTask(BaseModel):
    entity_table: str
    entity_column: str
    time_column: str
    horizon_days: int
    val_cutoff: str
    test_cutoff: str
    label_sql: str
    time_columns: dict[str, str | None]
    outcome_columns: list[str] = []
    framing: dict[str, str]


def render_structure_prompt(structure: dict, question: str) -> str:
    lines = [
        f"The person wants to predict: {question}",
        "",
        f"Derived structure ({len(structure['tables'])} linked tables):",
    ]
    for table in structure["tables"]:
        cols = ", ".join(f"{c['name']} ({c['type']})" for c in table["columns"])
        lines.append(f"- {table['name']} [{table['rows']} rows]: {cols}")
    lines.append("Validated links: " + "; ".join(structure["edges"]))
    lines.append(
        "Date-column candidates per table: " + json.dumps(structure["time_candidates"])
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


class GraphAuthor:
    def __init__(self, gateway: LLMGateway):
        self.gateway = gateway

    def author(self, table: QueryTable, structure: dict, question: str) -> AuthoredTask:
        """One authoring turn. ``table`` is the governance payload (schema/
        catalog metadata for the egress log); ``structure`` is the derived
        summary rendered into the prompt."""
        try:
            raw = self.gateway.run(
                _flatten((table,)),
                SYSTEM_PROMPT,
                lambda _capped: render_structure_prompt(structure, question),
            )
        except Exception as exc:  # noqa: BLE001 - ANY failure ends plainly
            raise GraphAuthoringError(
                f"The authoring guidance could not be produced ({exc}). "
                "Nothing was created — please try again."
            ) from exc
        try:
            authored = AuthoredTask.model_validate_json(_extract_json(raw))
        except (ValidationError, json.JSONDecodeError) as exc:
            raise GraphAuthoringError(
                f"The authoring response could not be understood: {exc}"
            ) from exc
        names = {t["name"] for t in structure["tables"]}
        if authored.entity_table not in names:
            raise GraphAuthoringError(
                f"The proposal named an unknown table "
                f"'{authored.entity_table}'. Nothing was created."
            )
        for tname, col in authored.time_columns.items():
            if tname not in names:
                raise GraphAuthoringError(
                    f"The proposal named an unknown table '{tname}'."
                )
            if col and col not in structure["time_candidates"].get(tname, []):
                raise GraphAuthoringError(f"'{col}' is not a date column of {tname}.")
        return authored
