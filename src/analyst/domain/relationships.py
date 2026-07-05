"""Relationship value object (feature 009) — a single-column PK/FK link.

A `Relationship` records that ``child_table.child_column`` references
``parent_table.parent_column``. It is either **declared** (read from a
database's own catalog) or **inferred** (proposed by the discovery engine and
validated by referential integrity). The join semantics are carried on the
relationship itself: an ``optional`` link (the child column has nulls) must be
LEFT-joined downstream so unmatched rows survive; a ``required`` link is an
inner join. Single-column only (composite keys are out of scope for 009).
"""

from __future__ import annotations

from dataclasses import dataclass

DECLARED = "declared"
INFERRED = "inferred"
REQUIRED = "required"
OPTIONAL = "optional"


@dataclass(frozen=True)
class Relationship:
    """One discovered single-column foreign-key relationship."""

    child_table: str
    child_column: str
    parent_table: str
    parent_column: str
    origin: str  # "declared" | "inferred"
    join_type: str  # "required" | "optional"
    coverage: float = 1.0  # RI match fraction of non-null child values (1.0 = full)

    @property
    def declared(self) -> bool:
        return self.origin == DECLARED

    @property
    def optional(self) -> bool:
        return self.join_type == OPTIONAL
