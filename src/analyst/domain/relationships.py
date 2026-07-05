"""Relationship value object (feature 009) — a PK/FK link.

A `Relationship` records that ``child_table.child_column`` references
``parent_table.parent_column``. It is either **declared** (read from a
database's own catalog) or **inferred** (proposed by the discovery engine and
validated by referential integrity). The join semantics are carried on the
relationship itself: an ``optional`` link (the child column has nulls) must be
LEFT-joined downstream so unmatched rows survive; a ``required`` link is an
inner join.

Composite (multi-column) keys are supported via ``extra_columns`` — additional
``(child, parent)`` column pairs beyond the primary one. A single-column FK
leaves it empty; ``column_pairs`` always yields the full join key. Kept as an
optional trailing field so every single-column construction site is unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass

DECLARED = "declared"
INFERRED = "inferred"
REQUIRED = "required"
OPTIONAL = "optional"


@dataclass(frozen=True)
class Relationship:
    """One discovered foreign-key relationship (single- or multi-column)."""

    child_table: str
    child_column: str
    parent_table: str
    parent_column: str
    origin: str  # "declared" | "inferred"
    join_type: str  # "required" | "optional"
    coverage: float = 1.0  # RI match fraction of non-null child values (1.0 = full)
    # Additional (child_column, parent_column) pairs for a composite key.
    extra_columns: tuple[tuple[str, str], ...] = ()

    @property
    def declared(self) -> bool:
        return self.origin == DECLARED

    @property
    def optional(self) -> bool:
        return self.join_type == OPTIONAL

    @property
    def is_composite(self) -> bool:
        return bool(self.extra_columns)

    @property
    def column_pairs(self) -> tuple[tuple[str, str], ...]:
        """Every (child_column, parent_column) pair — the full join key."""
        return ((self.child_column, self.parent_column), *self.extra_columns)
