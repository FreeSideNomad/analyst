"""Feature 012 — gallery fetch + the committed trainer, on REAL Ames data
(downloaded on demand into tests/.ml_cache, per the owner's directive)."""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import pytest

os.environ.setdefault("ANALYST_ML_CACHE", "tests/.ml_cache")

from analyst.engine.mlsamples import GALLERY, fetch_sample_csv, sample  # noqa: E402
from analyst.engine.mltrain import (  # noqa: E402
    PARAMETER_SCHEMA,
    LeakageError,
    train,
    validate_params,
)

FEATURES = [
    "OverallQual",
    "GrLivArea",
    "GarageCars",
    "TotalBsmtSF",
    "FullBath",
    "YearBuilt",
    "YearRemodAdd",
    "Neighborhood",
    "KitchenQual",
    "ExterQual",
    "LotArea",
    "Fireplaces",
    "BsmtFinSF1",
    "CentralAir",
    "MSZoning",
]


@pytest.fixture(scope="module")
def ames() -> pd.DataFrame:
    return pd.read_csv(fetch_sample_csv("ames"))


def test_gallery_entries_and_cache():
    assert [s.key for s in GALLERY] == ["ames", "king_county"]
    assert sample("ames").target == "SalePrice"
    path = fetch_sample_csv("ames")
    assert Path(path).is_file()
    mtime = Path(path).stat().st_mtime
    assert fetch_sample_csv("ames") == path  # cached — no re-download
    assert Path(path).stat().st_mtime == mtime


def test_ames_shape(ames):
    assert ames.shape == (1460, 81)
    assert "SalePrice" in ames.columns


def test_training_meets_real_thresholds(ames):
    result = train(ames, "SalePrice", FEATURES)
    assert result.metrics["gbm"]["r2"] >= 0.80
    assert result.metrics["gbm"]["r2"] > result.metrics["linear"]["r2"] - 0.05
    assert result.metrics["gbm"]["mae"] < 25_000
    assert result.row_count == 1460 and result.holdout_count == 292


def test_training_is_deterministic(ames):
    a = train(ames, "SalePrice", FEATURES)
    b = train(ames, "SalePrice", FEATURES)
    assert a.metrics == b.metrics
    assert a.importances == b.importances
    assert a.predictions["predicted"].equals(b.predictions["predicted"])


def test_target_leakage_is_structurally_rejected(ames):
    with pytest.raises(LeakageError):
        train(ames, "SalePrice", FEATURES + ["SalePrice"])
    with pytest.raises(LeakageError):
        train(ames, "SalePrice", [])
    with pytest.raises(LeakageError):
        train(ames, "SalePrice", ["NoSuchColumn"])


def test_predictions_cover_every_row_with_flags(ames):
    result = train(ames, "SalePrice", FEATURES)
    assert len(result.predictions) == 1460
    assert set(result.predictions.columns) == {"actual", "predicted", "is_holdout"}
    assert result.predictions["is_holdout"].sum() == 292


def test_importances_are_plain_feature_names(ames):
    result = train(ames, "SalePrice", FEATURES)
    names = [name for name, _ in result.importances]
    assert set(names) <= set(FEATURES)
    assert abs(sum(v for _, v in result.importances) - 1.0) < 0.01
    assert result.importances[0][1] > 0  # something actually matters


def test_parameter_bounds():
    clean = validate_params({})
    assert clean["n_estimators"] == PARAMETER_SCHEMA["n_estimators"]["default"]
    with pytest.raises(ValueError, match="between"):
        validate_params({"learning_rate": 5.0})
    with pytest.raises(ValueError, match="Unknown"):
        validate_params({"nope": 1})
