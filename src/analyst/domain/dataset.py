"""Dataset-level domain objects."""

from __future__ import annotations

from dataclasses import dataclass

from analyst.domain.profile import DatasetProfile


@dataclass(frozen=True)
class DatasetSummary:
    """One dataset produced by an ingestion (a file may yield several)."""

    name: str
    profile: DatasetProfile


@dataclass(frozen=True)
class IngestionResult:
    """The observable outcome of ingesting a source into one or more datasets."""

    datasets: tuple[DatasetSummary, ...]

    @property
    def dataset_name(self) -> str:
        """Convenience accessor for single-dataset ingests (CSV/TSV/JSON)."""
        return self.datasets[0].name

    @property
    def profile(self) -> DatasetProfile:
        """Convenience accessor for single-dataset ingests."""
        return self.datasets[0].profile
