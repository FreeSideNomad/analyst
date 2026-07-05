"""Semantic catalog domain objects (AC-4) and the LLM egress payload (AC-16)."""

from __future__ import annotations

from dataclasses import dataclass, field

from analyst.domain.profile import DatasetProfile
from analyst.domain.relationships import Relationship
from analyst.domain.types import ColumnType


@dataclass(frozen=True)
class ColumnDescription:
    """Agent-authored description + inferred role for a column."""

    name: str
    description: str
    role: str  # domain role, e.g. "identifier", "measure", "category", "timestamp"


@dataclass(frozen=True)
class Clarification:
    """A structured AskQuestion (AC-22): a question + concrete options."""

    question: str
    options: tuple[str, ...]
    column: str | None = None


@dataclass(frozen=True)
class CatalogEntry:
    """The per-dataset semantic catalog entry."""

    table_description: str
    columns: tuple[ColumnDescription, ...]
    clarifications: tuple[Clarification, ...] = ()
    # The relationships THIS table participates in (feature 009): FK links where
    # it is the child (references another table) or the parent (is referenced).
    relationships: tuple[Relationship, ...] = ()


# --------------------------------------------------------------------------- #
# Egress payload — the ONLY thing that may cross to the model (AC-16).
# By construction it carries schema + profiles + a capped sample; never bulk rows.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ColumnMetadata:
    name: str
    inferred_type: ColumnType
    null_rate: float
    distinct_count: int
    samples: tuple[object, ...]  # capped by the gateway


@dataclass(frozen=True)
class CatalogPayload:
    """Metadata-only payload sent to the model for cataloguing."""

    dataset: str
    row_count: int
    columns: tuple[ColumnMetadata, ...] = field(default_factory=tuple)


def payload_from_profile(dataset: str, profile: DatasetProfile) -> CatalogPayload:
    """Build the metadata-only egress payload from a dataset profile.

    Samples are sorted so the rendered prompt is deterministic (stable
    record/replay keys). Only metadata + samples — never bulk rows (AC-16).
    """
    columns = tuple(
        ColumnMetadata(
            name=col.name,
            inferred_type=col.inferred_type,
            null_rate=profile.null_rate(col.name),
            distinct_count=col.distinct_count,
            samples=tuple(sorted(col.samples, key=lambda v: str(v))),
        )
        for col in profile.columns
    )
    return CatalogPayload(dataset=dataset, row_count=profile.row_count, columns=columns)
