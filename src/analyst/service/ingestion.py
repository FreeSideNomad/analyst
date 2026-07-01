"""IngestionService — the application-layer facade the acceptance suite drives.

Slice A: orchestrate CSV read → materialize → deterministic profile.
"""
from __future__ import annotations

import dataclasses
import os
import re
from pathlib import Path

from analyst.domain.dataset import IngestionResult
from analyst.engine.store import DatasetStore


def _dataset_name_from_path(path: Path) -> str:
    """Derive a safe dataset name from a file's stem."""
    stem = path.stem.strip().lower()
    name = re.sub(r"[^a-z0-9]+", "_", stem).strip("_")
    return name or "dataset"


class IngestionService:
    """Orchestrates ingestion. Thin — no bulk data handling of its own."""

    def __init__(self, store: DatasetStore):
        self.store = store

    def ingest(self, source: str | os.PathLike[str]) -> IngestionResult:
        path = Path(source)
        dataset = _dataset_name_from_path(path)
        plan = self.store.materialize_csv(dataset, path)
        profile = self.store.profile(dataset)
        profile = dataclasses.replace(
            profile,
            encoding=plan.encoding,
            synthesized_headers=plan.synthesized_headers,
            had_duplicate_columns=plan.had_duplicate_columns,
        )
        return IngestionResult(dataset_name=dataset, profile=profile)
