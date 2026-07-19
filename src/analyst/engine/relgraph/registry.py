"""Dataset discovery, adapted for analyst: knowledge-layer dataset
directories ship as package data under this package's `datasets/`, and the
cache roots under ANALYST_ML_CACHE (shared with the 012 sample gallery)."""

from __future__ import annotations

import os
from pathlib import Path

from .errors import RelgraphError
from .schema import DatasetSpec, list_task_names, load_dataset_spec


def datasets_root() -> Path:
    return Path(__file__).resolve().parent / "datasets"


def cache_root() -> Path:
    base = Path(os.environ.get("ANALYST_ML_CACHE", "/data/ml-cache"))
    return base / "relgraph"


def dataset_dir(name: str) -> Path:
    d = datasets_root() / name
    if not (d / "schema.yaml").is_file():
        raise RelgraphError(
            f"unknown dataset '{name}': no schema.yaml under {d} "
            f"(datasets root: {datasets_root()})"
        )
    return d


def get_spec(name: str) -> DatasetSpec:
    return load_dataset_spec(dataset_dir(name))


def discover() -> list[tuple[str, list[str]]]:
    """All datasets under the root with a valid schema.yaml, plus task names."""
    root = datasets_root()
    found: list[tuple[str, list[str]]] = []
    if not root.is_dir():
        return found
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        if not (d / "schema.yaml").is_file():
            continue
        try:
            spec = load_dataset_spec(d)
        except Exception:  # noqa: BLE001 - invalid schema: not listed
            continue
        found.append((spec.name, list_task_names(d)))
    return found
