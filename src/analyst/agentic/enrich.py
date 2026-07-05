"""Data-grounded catalog enrichment (feature 009) — deterministic, LLM-free.

Produces a `CatalogEntry` whose column descriptions are grounded in the real
name, type, cardinality, null rate, sampled values and any FK relationship
(AC-8), and whose table description aggregates the columns AND the relationships
the table participates in (AC-9). It is computed entirely locally, so it is
deterministic and governance-safe (no egress at all).

This is the default cataloguer for connected-database tables and the offline
path; the live LLM `Cataloguer` (agentic/cataloguer.py) is used when a cassette
or `ANALYST_CATALOG=live` is configured, and is fed the same distribution +
relationships so its output is grounded too.
"""

from __future__ import annotations

from analyst.domain.catalog import CatalogEntry, ColumnDescription
from analyst.domain.profile import ColumnProfile, DatasetProfile
from analyst.domain.relationships import Relationship
from analyst.domain.types import ColumnType

_NUMERIC = {ColumnType.INTEGER, ColumnType.DECIMAL}
_LOW_CARD = 25


def _role(col: ColumnProfile, is_child_fk: bool, is_key: bool) -> str:
    if is_child_fk or is_key:
        return "identifier"
    if col.inferred_type in _NUMERIC:
        return "measure"
    if col.inferred_type in {ColumnType.DATE, ColumnType.DATETIME}:
        return "timestamp"
    if col.inferred_type is ColumnType.BOOLEAN:
        return "category"
    if col.distinct_count and col.distinct_count <= _LOW_CARD:
        return "category"
    return "text"


def _sample_phrase(col: ColumnProfile, limit: int = 3) -> str:
    values = [str(v) for v in col.samples[:limit] if v is not None]
    return ", ".join(values)


def _null_note(col: ColumnProfile, row_count: int) -> str:
    if col.null_count <= 0 or row_count <= 0:
        return ""
    pct = col.null_count / row_count * 100
    return f" {pct:.0f}% of values are missing."


def _column_description(
    col: ColumnProfile,
    row_count: int,
    fk: Relationship | None,
    is_key: bool,
) -> str:
    name = col.name
    if fk is not None:
        opt = "optional" if fk.optional else "required"
        return (
            f"Foreign key: each {name} references {fk.parent_table}."
            f"{fk.parent_column} ({opt}).{_null_note(col, row_count)}"
        )
    if is_key:
        return (
            f"Primary key of the table — {col.distinct_count} unique {name} "
            f"values, e.g. {_sample_phrase(col)}."
        )
    if col.inferred_type in _NUMERIC:
        span = ""
        if col.minimum is not None and col.maximum is not None:
            span = f", ranging {col.minimum} to {col.maximum}"
        return (
            f"Numeric {name} — {col.distinct_count} distinct values{span}."
            f"{_null_note(col, row_count)}"
        )
    if col.inferred_type in {ColumnType.DATE, ColumnType.DATETIME}:
        span = ""
        if col.minimum is not None and col.maximum is not None:
            span = f" from {col.minimum} to {col.maximum}"
        return f"Date/time {name}{span}.{_null_note(col, row_count)}"
    if col.inferred_type is ColumnType.BOOLEAN:
        return f"Boolean flag {name}.{_null_note(col, row_count)}"
    samples = _sample_phrase(col)
    lead = f"Categorical {name}" if col.distinct_count <= _LOW_CARD else f"Text {name}"
    tail = f", e.g. {samples}" if samples else ""
    return (
        f"{lead} — {col.distinct_count} distinct values across {row_count} rows"
        f"{tail}.{_null_note(col, row_count)}"
    )


def _table_description(
    name: str, profile: DatasetProfile, relationships: tuple[Relationship, ...]
) -> str:
    n_cols = len(profile.columns)
    parts = [f"{name}: {profile.row_count} rows, {n_cols} columns."]
    parents = sorted({r.parent_table for r in relationships if r.child_table == name})
    children = sorted({r.child_table for r in relationships if r.parent_table == name})
    if parents:
        via = {
            r.parent_table: r.child_column
            for r in relationships
            if r.child_table == name
        }
        refs = ", ".join(f"{p} (via {via[p]})" for p in parents)
        parts.append(f"References {refs}.")
    if children:
        parts.append(f"Referenced by {', '.join(children)}.")
    return " ".join(parts)


def catalog_entry(
    table: str,
    profile: DatasetProfile,
    relationships: tuple[Relationship, ...] = (),
    keys: tuple[str, ...] = (),
) -> CatalogEntry:
    """Build a data-grounded CatalogEntry for one table (deterministic)."""
    mine = tuple(r for r in relationships if table in (r.child_table, r.parent_table))
    child_fk = {r.child_column: r for r in mine if r.child_table == table}
    key_set = set(keys)
    columns = tuple(
        ColumnDescription(
            name=col.name,
            description=_column_description(
                col,
                profile.row_count,
                child_fk.get(col.name),
                col.name in key_set,
            ),
            role=_role(col, col.name in child_fk, col.name in key_set),
        )
        for col in profile.columns
    )
    return CatalogEntry(
        table_description=_table_description(table, profile, mine),
        columns=columns,
        clarifications=(),
        relationships=mine,
    )
