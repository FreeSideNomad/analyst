"""Dataset-level domain objects."""
from __future__ import annotations

from dataclasses import dataclass

from analyst.domain.profile import DatasetProfile


@dataclass(frozen=True)
class IngestionResult:
    """The observable outcome of ingesting a file into a dataset."""

    dataset_name: str
    profile: DatasetProfile
