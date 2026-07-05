"""Wire schemas — pydantic mirrors of the domain, emitted as camelCase JSON.

Feature 001 shapes (Dataset/Profile/Catalog) mirror `analyst.domain.*` exactly
via `from_domain`. Feature 002 (Q&A) shapes are marked PROVISIONAL: the domain
has no query/answer model yet, only the `Clarification` primitive, which the
ClarificationResult mirrors.
"""

from __future__ import annotations

from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from analyst.domain.catalog import CatalogEntry, Clarification, ColumnDescription
from analyst.domain.profile import ColumnProfile, DatasetProfile
from analyst.domain.relationships import Relationship


class Camel(BaseModel):
    """Base: accept snake_case in, emit camelCase out."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    def dump(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True)


# --------------------------------------------------------------------------- #
# Feature 001 — profiling / catalog (mirror analyst.domain.*)
# --------------------------------------------------------------------------- #
class ColumnProfileSchema(Camel):
    name: str
    inferred_type: str
    null_count: int
    null_rate: float
    distinct_count: int
    samples: list[Any] = []
    minimum: Optional[Any] = None
    maximum: Optional[Any] = None
    quantiles: list[Any] = []
    is_mixed: bool = False
    dominant_type: Optional[str] = None
    off_type_examples: list[Any] = []
    is_nested: bool = False
    distribution: list[dict] = []  # [{label, count}] — real value distribution

    @classmethod
    def from_domain(cls, col: ColumnProfile, null_rate: float) -> "ColumnProfileSchema":
        return cls(
            name=col.name,
            inferred_type=col.inferred_type.value,
            null_count=col.null_count,
            null_rate=null_rate,
            distinct_count=col.distinct_count,
            samples=list(col.samples),
            minimum=col.minimum,
            maximum=col.maximum,
            quantiles=list(col.quantiles),
            is_mixed=col.is_mixed,
            dominant_type=col.dominant_type.value if col.dominant_type else None,
            off_type_examples=list(col.off_type_examples),
            is_nested=col.is_nested,
            distribution=[
                {"label": b.label, "count": b.count} for b in col.distribution
            ],
        )


class DatasetProfileSchema(Camel):
    row_count: int
    columns: list[ColumnProfileSchema] = []
    encoding: Optional[str] = None
    synthesized_headers: bool = False
    had_duplicate_columns: bool = False

    @classmethod
    def from_domain(cls, p: DatasetProfile) -> "DatasetProfileSchema":
        return cls(
            row_count=p.row_count,
            columns=[
                ColumnProfileSchema.from_domain(c, p.null_rate(c.name))
                for c in p.columns
            ],
            encoding=p.encoding,
            synthesized_headers=p.synthesized_headers,
            had_duplicate_columns=p.had_duplicate_columns,
        )


class ColumnDescriptionSchema(Camel):
    name: str
    description: str
    role: str

    @classmethod
    def from_domain(cls, c: ColumnDescription) -> "ColumnDescriptionSchema":
        return cls(name=c.name, description=c.description, role=c.role)


class ClarificationSchema(Camel):
    question: str
    options: list[str] = []
    column: Optional[str] = None

    @classmethod
    def from_domain(cls, c: Clarification) -> "ClarificationSchema":
        return cls(question=c.question, options=list(c.options), column=c.column)


class RelationshipSchema(Camel):
    """A FK relationship (feature 009), origin + join semantics. Multi-column
    (composite) keys carry their additional column pairs in ``extraColumns``."""

    child_table: str
    child_column: str
    parent_table: str
    parent_column: str
    origin: str  # "declared" | "inferred"
    join_type: str  # "required" | "optional"
    coverage: float = 1.0
    extra_columns: list[list[str]] = []  # [[childCol, parentCol], ...] for composite

    @classmethod
    def from_domain(cls, r: Relationship) -> "RelationshipSchema":
        return cls(
            child_table=r.child_table,
            child_column=r.child_column,
            parent_table=r.parent_table,
            parent_column=r.parent_column,
            origin=r.origin,
            join_type=r.join_type,
            coverage=r.coverage,
            extra_columns=[[c, p] for c, p in r.extra_columns],
        )


class CatalogEntrySchema(Camel):
    table_description: str
    columns: list[ColumnDescriptionSchema] = []
    clarifications: list[ClarificationSchema] = []
    relationships: list[RelationshipSchema] = []

    @classmethod
    def from_domain(cls, e: CatalogEntry) -> "CatalogEntrySchema":
        return cls(
            table_description=e.table_description,
            columns=[ColumnDescriptionSchema.from_domain(c) for c in e.columns],
            clarifications=[
                ClarificationSchema.from_domain(c) for c in e.clarifications
            ],
            relationships=[RelationshipSchema.from_domain(r) for r in e.relationships],
        )


class DatasetSchema(Camel):
    """API envelope: the pure domain profile/catalog + repository metadata."""

    id: str
    name: str
    file_name: str
    status: str
    ingested_at: Optional[str] = None
    row_count: int
    column_count: int
    profile: DatasetProfileSchema
    catalog: Optional[CatalogEntrySchema] = None
    # Feature 006 — source-grouped workbench (file/connection → table → columns):
    group: (
        str  # the FILE with extension ("company.xlsx") or the connection ("sales_db")
    )
    entity: str  # the sheet/table/stem shown as the table node ("employees", "orders")
    source_kind: str  # "file" | "database" (from DatasetRecord.federated)
    queryable: bool  # False for connected-DB tables (not yet Q&A-answerable)
    # Feature 009 — async cataloguing lifecycle: "complete" | "pending" | "failed".
    catalog_status: str = "complete"


class IngestionResultSchema(Camel):
    datasets: list[DatasetSchema] = []


class IngestionStatusSchema(Camel):
    dataset: str
    status: str  # domain IngestionStatus: "in progress" | "complete" | "failed"
    phase: Optional[str] = None  # UI hint (not domain-authoritative)
    progress: Optional[int] = None  # 0..100 UI hint


class RefreshResultSchema(Camel):
    dataset_name: str
    replaced: bool
    version: Optional[int] = None
    clarification: Optional[ClarificationSchema] = None
    profile: Optional[DatasetProfileSchema] = None


# --------------------------------------------------------------------------- #
# Feature 002 — Q&A (PROVISIONAL: no domain model yet)
# --------------------------------------------------------------------------- #
class ChartPoint(Camel):
    label: str
    value: float


class TrustTrailSchema(Camel):
    assumptions: list[str] = []
    lineage: list[str] = []
    sql: str = ""


class StatBlock(Camel):
    value: str
    label: str
    sub: str


class TableBlock(Camel):
    """The locally-computed result as a table (feature: result-table view). Rows
    are already capped by the engine; the browser paginates + can save/download."""

    columns: list[str] = []
    rows: list[list[Any]] = []
    truncated: bool = False


class ClarificationResult(Camel):
    type: Literal["clarification"] = "clarification"
    query_id: str
    question: str
    options: list[str] = []
    column: Optional[str] = None


class AnswerResult(Camel):
    type: Literal["answer"] = "answer"
    query_id: str
    summary: str
    chart_type: str = "none"  # "bar" | "stat" | "none"
    abstain: bool = False
    chart_title: Optional[str] = None
    highlight: Optional[str] = None
    nice_max: Optional[float] = None
    tick_step: Optional[float] = None
    chart_data: Optional[list[ChartPoint]] = None
    stat: Optional[StatBlock] = None
    table: Optional[TableBlock] = None  # the full result for the table view
    trust_trail: Optional[TrustTrailSchema] = None


QueryResult = Union[ClarificationResult, AnswerResult]


class QueryRequest(Camel):
    question: str
    dataset_ids: Optional[list[str]] = None


class RespondRequest(Camel):
    selected_options: list[str] = []
