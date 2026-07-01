"""Profiling value objects (AC-2)."""
from __future__ import annotations

from dataclasses import dataclass, field

from analyst.domain.types import ColumnType


@dataclass(frozen=True)
class ColumnProfile:
    """Deterministic profile of a single column."""

    name: str
    inferred_type: ColumnType
    null_count: int
    distinct_count: int
    samples: tuple[object, ...] = ()

    @property
    def null_rate(self) -> float:
        """Fraction of values that are null, given the dataset row count."""
        # null_rate needs the row count; exposed via DatasetProfile.null_rate.
        raise NotImplementedError  # pragma: no cover


@dataclass(frozen=True)
class DatasetProfile:
    """Deterministic profile of a whole dataset."""

    row_count: int
    columns: tuple[ColumnProfile, ...] = field(default_factory=tuple)

    def null_rate(self, column_name: str) -> float:
        """Null fraction for a column (0.0 when there are no rows)."""
        if self.row_count == 0:
            return 0.0
        col = next(c for c in self.columns if c.name == column_name)
        return col.null_count / self.row_count
