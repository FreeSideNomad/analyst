"""ML sample gallery — feature 012 (engine layer).

Real datasets, downloaded ON DEMAND and cached locally (owner directive:
never stored in git; the cache makes the acceptance feedback loop cheap and
repeat adds offline). Each entry pins an exact OpenML snapshot so training
is reproducible down to the row.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SampleDataset:
    key: str
    title: str
    openml_id: int
    target: str
    description: str


GALLERY: tuple[SampleDataset, ...] = (
    SampleDataset(
        key="ames",
        title="Ames house prices",
        openml_id=42165,
        target="SalePrice",
        description=(
            "1,460 real home sales (Ames, Iowa) with 80 attributes — the "
            "classic learning dataset for price prediction."
        ),
    ),
    SampleDataset(
        key="king_county",
        title="King County house sales",
        openml_id=42092,
        target="price",
        description=(
            "21,613 real sales around Seattle with 21 attributes including location."
        ),
    ),
)


class UnknownSampleError(KeyError):
    """Asked for a gallery entry that does not exist."""


def sample(key: str) -> SampleDataset:
    for entry in GALLERY:
        if entry.key == key:
            return entry
    raise UnknownSampleError(key)


def cache_dir() -> Path:
    return Path(os.environ.get("ANALYST_ML_CACHE", "/data/ml-cache"))


def fetch_sample_csv(key: str) -> Path:
    """The sample as a CSV on disk — downloading once, cached thereafter.

    The CSV feeds the NORMAL ingestion pipeline; from there the dataset is
    profiled/catalogued like any upload (AC-1).
    """
    entry = sample(key)
    cache = cache_dir()
    cache.mkdir(parents=True, exist_ok=True)
    csv_path = cache / f"{entry.key}.csv"
    if csv_path.is_file():
        return csv_path
    import shutil

    from sklearn.datasets import fetch_openml

    def _fetch():  # type: ignore[no-untyped-def]
        return fetch_openml(
            data_id=entry.openml_id,
            as_frame=True,
            data_home=str(cache / "openml"),
            parser="auto",
        )

    try:
        fetched = _fetch()
    except ValueError:
        # A corrupt/partial download stays in the openml cache and fails
        # its checksum forever — clear it and retry once from scratch.
        shutil.rmtree(cache / "openml", ignore_errors=True)
        fetched = _fetch()
    frame = fetched.frame
    tmp = csv_path.with_suffix(".tmp")
    frame.to_csv(tmp, index=False)
    tmp.rename(csv_path)
    return csv_path
