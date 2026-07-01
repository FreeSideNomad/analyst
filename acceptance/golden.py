"""Golden-corpus datasets for AC-24 — real Kaggle-sourced data with ground truth.

Datasets are downloaded at test time (cached, gitignored) — not committed, to
respect licensing (see docs/golden-corpus.md). The documented ground truth
(row count + per-column type/null-rate/cardinality) is committed and asserted
against the live profiling within tolerance.
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

from analyst.domain.profile import DatasetProfile

_ROOT = Path(__file__).parent.parent
CACHE_DIR = _ROOT / "tests" / ".golden_cache"
GROUND_TRUTH = _ROOT / "tests" / "golden" / "ground_truth.json"

GOLDEN_URLS: dict[str, tuple[str, str]] = {
    "titanic": (
        "https://raw.githubusercontent.com/datasciencedojo/datasets/master/titanic.csv",
        ".csv",
    ),
    "messy_imdb": (
        "https://raw.githubusercontent.com/eyowhite/Messy-dataset/main/messy_IMDB_dataset.csv",
        ".csv",
    ),
    "messy_hr": (
        "https://raw.githubusercontent.com/eyowhite/Messy-dataset/main/messy_HR_data.csv",
        ".csv",
    ),
    "superstore": (
        "https://github.com/PacktPublishing/Tableau-10-Best-Practices/raw/master/"
        "Chapter%205/Sample%20-%20Superstore%20Sales%20(Excel).xls",
        ".xls",
    ),
}


def download(name: str) -> Path:
    url, ext = GOLDEN_URLS[name]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{name}{ext}"
    if not path.exists():
        request = urllib.request.Request(
            url, headers={"User-Agent": "analyst-golden/1"}
        )
        with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
            path.write_bytes(response.read())
    return path


def profile_facts(profile: DatasetProfile) -> dict:
    """The ground-truth-relevant facts of a profile."""
    return {
        "row_count": profile.row_count,
        "columns": {
            col.name: {
                "type": col.inferred_type.value,
                "null_rate": round(profile.null_rate(col.name), 2),
                "distinct": col.distinct_count,
            }
            for col in profile.columns
        },
    }


def load_ground_truth() -> dict:
    return json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))
