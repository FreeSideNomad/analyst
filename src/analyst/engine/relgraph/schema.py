"""Knowledge-layer model: typed specs loaded from a dataset directory.

The engine knows nothing about any concrete dataset; everything it does is
driven by these specs (Fowler's knowledge level). Validation happens at load
time, before any data file is read.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .errors import RelgraphError

DUCKDB_TYPES = {
    "string": "VARCHAR",
    "int": "BIGINT",
    "float": "DOUBLE",
    "bool": "BOOLEAN",
    "date": "DATE",
    "timestamp": "TIMESTAMP",
}


@dataclass
class ColumnSpec:
    name: str
    type: str

    @property
    def duckdb_type(self) -> str:
        try:
            return DUCKDB_TYPES[self.type]
        except KeyError:
            raise RelgraphError(
                f"unknown column type '{self.type}' for column '{self.name}' "
                f"(known: {', '.join(sorted(DUCKDB_TYPES))})"
            )


@dataclass
class ForeignKeySpec:
    column: str
    ref_table: str
    ref_column: str


@dataclass
class TableSpec:
    name: str
    file: str
    primary_key: str
    columns: list[ColumnSpec]
    time_column: str | None = None
    temporal: bool = False
    delimiter: str = ","
    encoding: str = "utf-8"
    foreign_keys: list[ForeignKeySpec] = field(default_factory=list)
    # Derived tables have no source file: the dataset's hook materializes
    # them at build time from previously loaded tables.
    derived: bool = False

    @property
    def is_temporal(self) -> bool:
        return self.temporal or self.time_column is not None

    def column(self, name: str) -> ColumnSpec | None:
        return next((c for c in self.columns if c.name == name), None)


@dataclass
class SourceSpec:
    name: str
    url: str
    filename: str
    sha256: str | None = None
    fallback_url: str | None = None
    archive: str | None = None  # e.g. "zip"
    kind: str = "http"  # "http" (also file://) or "kaggle"


@dataclass
class DatasetSpec:
    name: str
    root: Path
    val_timestamp: str
    test_timestamp: str
    sources: list[SourceSpec]
    tables: dict[str, TableSpec]

    def table(self, name: str) -> TableSpec:
        try:
            return self.tables[name]
        except KeyError:
            raise RelgraphError(f"dataset '{self.name}' has no table '{name}'")


@dataclass
class TaskSpec:
    name: str
    dataset: str
    entity_table: str
    entity_column: str
    time_column: str
    horizon_days: int
    metric: str
    label_query: str
    # Columns hidden from models for this task ("table.column"): outcome
    # columns that encode the label or post-as-of information.
    exclude: list[str] = field(default_factory=list)
    # Optional graph-model hints (num_layers, num_neighbors) — knowledge-layer
    # metadata, e.g. when the signal sits more hops away than the default.
    graph: dict = field(default_factory=dict)
    # Plain-language framing shown to the user when the task is defined
    # (question, what the prediction moment means, why outcomes are hidden).
    framing: dict = field(default_factory=dict)

    def excluded_columns(self, table: str) -> set[str]:
        out = set()
        for item in self.exclude:
            t, _, c = item.partition(".")
            if t == table and c:
                out.add(c)
        return out


def load_dataset_spec(dataset_dir: Path) -> DatasetSpec:
    path = dataset_dir / "schema.yaml"
    if not path.is_file():
        raise RelgraphError(f"no schema.yaml in {dataset_dir}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))

    sources = [
        SourceSpec(
            name=s["name"],
            url=s["url"],
            filename=s["filename"],
            sha256=s.get("sha256"),
            fallback_url=s.get("fallback_url"),
            archive=s.get("archive"),
            kind=s.get("kind", "http"),
        )
        for s in raw.get("sources", [])
    ]
    tables: dict[str, TableSpec] = {}
    for tname, t in (raw.get("tables") or {}).items():
        tables[tname] = TableSpec(
            name=tname,
            file=t.get("file", ""),
            derived=bool(t.get("derived", False)),
            primary_key=t["primary_key"],
            columns=[ColumnSpec(c["name"], c["type"]) for c in t.get("columns", [])],
            time_column=t.get("time_column"),
            temporal=bool(t.get("temporal", False)),
            delimiter=t.get("delimiter", ","),
            encoding=t.get("encoding", "utf-8"),
            foreign_keys=[
                ForeignKeySpec(
                    column=fk["column"],
                    ref_table=fk["references"]["table"],
                    ref_column=fk["references"]["column"],
                )
                for fk in t.get("foreign_keys", [])
            ],
        )
    spec = DatasetSpec(
        name=raw.get("name", dataset_dir.name),
        root=dataset_dir,
        val_timestamp=str(raw["val_timestamp"]),
        test_timestamp=str(raw["test_timestamp"]),
        sources=sources,
        tables=tables,
    )
    validate_dataset_spec(spec)
    return spec


def validate_dataset_spec(spec: DatasetSpec) -> None:
    """Metadata validation. Runs before any data file is read."""
    for table in spec.tables.values():
        if not table.derived and not table.file:
            raise RelgraphError(
                f"metadata validation error: table '{table.name}' declares no "
                f"file and is not marked derived"
            )
        if table.temporal and not table.time_column:
            raise RelgraphError(
                f"metadata validation error: table '{table.name}' is declared "
                f"temporal but names no time column"
            )
        if table.time_column and not table.column(table.time_column):
            raise RelgraphError(
                f"metadata validation error: table '{table.name}' declares time "
                f"column '{table.time_column}' which is not among its columns"
            )
        if table.columns and not table.column(table.primary_key):
            raise RelgraphError(
                f"metadata validation error: table '{table.name}' declares "
                f"primary key '{table.primary_key}' which is not among its columns"
            )
        for fk in table.foreign_keys:
            if fk.ref_table not in spec.tables:
                raise RelgraphError(
                    f"metadata validation error: foreign key on table "
                    f"'{table.name}', column '{fk.column}' references unknown "
                    f"table '{fk.ref_table}'"
                )
            if not table.column(fk.column) and table.columns:
                raise RelgraphError(
                    f"metadata validation error: foreign key column "
                    f"'{fk.column}' is not among table '{table.name}' columns"
                )
        for col in table.columns:
            col.duckdb_type  # raises on unknown type


def load_task_spec(dataset_dir: Path, dataset_name: str, task_name: str) -> TaskSpec:
    path = dataset_dir / "tasks" / f"{task_name}.yaml"
    if not path.is_file():
        available = sorted(p.stem for p in (dataset_dir / "tasks").glob("*.yaml"))
        raise RelgraphError(
            f"dataset '{dataset_name}' has no task '{task_name}' "
            f"(available: {', '.join(available) or 'none'})"
        )
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return TaskSpec(
        name=raw.get("name", task_name),
        dataset=dataset_name,
        entity_table=raw["entity_table"],
        entity_column=raw["entity_column"],
        time_column=raw["time_column"],
        horizon_days=int(raw["horizon_days"]),
        metric=raw.get("metric", "auroc"),
        label_query=raw["label_query"],
        exclude=list(raw.get("exclude", [])),
        graph=dict(raw.get("graph", {})),
        framing=dict(raw.get("framing", {})),
    )


def list_task_names(dataset_dir: Path) -> list[str]:
    tasks_dir = dataset_dir / "tasks"
    if not tasks_dir.is_dir():
        return []
    return sorted(p.stem for p in tasks_dir.glob("*.yaml"))
