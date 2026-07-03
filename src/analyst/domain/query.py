"""Q&A domain model (feature 003).

Pure value objects for confidence-gated natural-language answering:
- QueryTable / QueryColumn — the *metadata* a planner may see (schema,
  profile facts, capped sorted samples, catalog descriptions). Never bulk rows.
- QueryPlan — the planner's structured decision: answer / clarify / abstain.
- ResultTable — a small, locally computed result set.

No I/O, no framework imports (CHARTER §2).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from analyst.domain.catalog import Clarification
from analyst.domain.dataset import DatasetSummary
from analyst.domain.types import ColumnType


class PlanAction(str, Enum):
    """The confidence-gated outcomes of planning a question (FR-11)."""

    ANSWER = "answer"
    CLARIFY = "clarify"
    ABSTAIN = "abstain"


@dataclass(frozen=True)
class QueryColumn:
    """Column metadata the planner sees — schema + profile facts, never data."""

    name: str
    inferred_type: ColumnType
    null_rate: float
    distinct_count: int
    samples: tuple[object, ...] = ()
    description: str = ""
    role: str = ""


@dataclass(frozen=True)
class QueryTable:
    """One dataset's metadata as presented to the planner."""

    name: str
    row_count: int
    description: str = ""
    columns: tuple[QueryColumn, ...] = ()


@dataclass(frozen=True)
class QueryPlan:
    """The planner's structured decision for one question."""

    action: PlanAction
    confidence: float = 0.0
    sql: str | None = None
    title: str | None = None
    assumptions: tuple[str, ...] = ()
    lineage: tuple[str, ...] = ()
    clarification: Clarification | None = None
    reason: str | None = None


@dataclass(frozen=True)
class ResultTable:
    """A small local result set (capped by the engine helper)."""

    columns: tuple[str, ...]
    rows: tuple[tuple[object, ...], ...]
    truncated: bool = False


def query_table_from_summary(summary: DatasetSummary) -> QueryTable:
    """Build the planner-facing metadata for one dataset.

    Samples are sorted (stable record/replay prompt keys) and descriptions are
    joined in from the semantic catalog when present — planning targets the
    catalog, not raw schema (CHARTER §2).
    """
    catalog = summary.catalog
    described = {c.name: c for c in catalog.columns} if catalog else {}
    columns = tuple(
        QueryColumn(
            name=col.name,
            inferred_type=col.inferred_type,
            null_rate=summary.profile.null_rate(col.name),
            distinct_count=col.distinct_count,
            samples=tuple(sorted(col.samples, key=lambda v: str(v))),
            description=(
                described[col.name].description if col.name in described else ""
            ),
            role=described[col.name].role if col.name in described else "",
        )
        for col in summary.profile.columns
    )
    return QueryTable(
        name=summary.name,
        row_count=summary.profile.row_count,
        description=catalog.table_description if catalog else "",
        columns=columns,
    )
