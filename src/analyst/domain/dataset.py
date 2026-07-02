"""Dataset-level domain objects."""

from __future__ import annotations

from dataclasses import dataclass

from analyst.domain.catalog import CatalogEntry, Clarification
from analyst.domain.profile import DatasetProfile


@dataclass(frozen=True)
class DatasetSummary:
    """One dataset produced by an ingestion (a file may yield several)."""

    name: str
    profile: DatasetProfile
    catalog: CatalogEntry | None = None


@dataclass(frozen=True)
class RefreshResult:
    """Outcome of refreshing a dataset (AC-18, AC-19).

    replaced=True → new data validated and installed as a new version.
    clarification set → non-conforming data; the user is asked to loosen first.
    """

    dataset_name: str
    replaced: bool
    version: int | None = None
    clarification: Clarification | None = None
    profile: DatasetProfile | None = None


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
