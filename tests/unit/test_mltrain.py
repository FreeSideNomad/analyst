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


def test_corrupt_download_is_cleared_and_retried(tmp_path, monkeypatch):
    # A partial/corrupt OpenML download fails its checksum forever unless the
    # openml cache is cleared — fetch_sample_csv must recover in one retry.
    import sklearn.datasets

    monkeypatch.setenv("ANALYST_ML_CACHE", str(tmp_path))
    (tmp_path / "openml").mkdir()
    (tmp_path / "openml" / "corrupt.arff").write_text("garbage")
    calls: list[int] = []

    def fake_fetch(**kwargs):
        calls.append(1)
        if (tmp_path / "openml").exists():
            raise ValueError("md5 checksum of local file does not match")

        class Fetched:
            frame = pd.DataFrame({"SalePrice": [1, 2]})

        return Fetched()

    monkeypatch.setattr(sklearn.datasets, "fetch_openml", fake_fetch)
    path = fetch_sample_csv("ames")
    assert len(calls) == 2  # failed once, cache cleared, succeeded
    assert not (tmp_path / "openml").exists()
    assert Path(path).is_file()


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


# --------------------------------------------------------------------------- #
# Repository lifecycle over the REAL cached Ames data
# --------------------------------------------------------------------------- #
from analyst.agentic.models import (  # noqa: E402
    FeatureProposal,
    GuidanceResult,
    ModelGuidanceError,
)
from analyst.api.repository import StoreRepository  # noqa: E402
from analyst.domain.models import UnknownModelError  # noqa: E402


class StubGuide:
    def __init__(self, fail: bool = False):
        self.fail = fail

    def guide(self, table, target):
        if self.fail:
            raise ModelGuidanceError("guidance failed")
        return GuidanceResult(
            teaching_note="Predicting SalePrice is like fitting a line, but bendier.",
            split_note="I'll hide 20% of the homes and grade myself on them.",
            features=[
                FeatureProposal(name=f, reason=f"{f} drives price.") for f in FEATURES
            ],
        )


def _repo_with_ames(tmp_path) -> tuple[StoreRepository, str]:
    repo = StoreRepository(str(tmp_path / "data"), model_guide=StubGuide())
    record = repo.add_sample("ames")
    return repo, record.name


def test_add_sample_ingests_and_is_idempotent(tmp_path):
    repo, name = _repo_with_ames(tmp_path)
    assert name == "ames.csv"
    record = repo.get_dataset(name)
    assert record.summary.profile.row_count == 1460
    assert len(record.summary.profile.columns) == 81
    again = repo.add_sample("ames")
    assert again.name == name and len(repo.list_datasets()) == 1


def test_task_lifecycle_to_trained_model(tmp_path):
    repo, name = _repo_with_ames(tmp_path)
    task = repo.create_model_task(name, "SalePrice")
    assert task["status"] == "defined"
    assert task["teaching_note"] and task["split_note"]
    assert len(task["proposed"]) == len(FEATURES)

    task = repo.update_task_features(task["task_id"], FEATURES[:-1])
    assert len(task["accepted"]) == len(FEATURES) - 1

    task = repo.train_model(task["task_id"])
    assert task["status"] == "trained"
    assert task["metrics"]["gbm"]["r2"] >= 0.80
    predictions = repo.get_dataset(task["predictions_dataset"])
    assert predictions is not None
    assert predictions.summary.profile.row_count == 1460
    counts = repo.store.value_counts(task["predictions_dataset"], "model")
    assert counts == {f"{task['task_id']} v1": 1460}


def test_registry_persists_across_restart(tmp_path):
    repo, name = _repo_with_ames(tmp_path)
    task = repo.create_model_task(name, "SalePrice")
    repo.train_model(task["task_id"])
    reborn = StoreRepository(str(tmp_path / "data"))
    (listed,) = reborn.models()
    assert listed["status"] == "trained" and listed["metrics"]["gbm"]["r2"] >= 0.80
    assert reborn.get_dataset(listed["predictions_dataset"]) is not None


def test_guardrails(tmp_path):
    repo, name = _repo_with_ames(tmp_path)
    task = repo.create_model_task(name, "SalePrice")
    with pytest.raises(LeakageError):
        repo.update_task_features(task["task_id"], ["SalePrice"])
    with pytest.raises(ValueError):
        repo.update_task_features(task["task_id"], [])
    with pytest.raises(UnknownModelError):
        repo.model("nope")
    with pytest.raises(ValueError):
        repo.create_model_task(name, "NoSuchColumn")


def test_failed_guidance_creates_nothing(tmp_path):
    repo = StoreRepository(str(tmp_path / "data"), model_guide=StubGuide(fail=True))
    repo.add_sample("ames")
    with pytest.raises(ModelGuidanceError):
        repo.create_model_task("ames.csv", "SalePrice")
    assert repo.models() == []


def test_offline_task_creation_is_honest(tmp_path):
    repo = StoreRepository(str(tmp_path / "data"))
    repo.add_sample("ames")
    with pytest.raises(ModelGuidanceError, match="AI"):
        repo.create_model_task("ames.csv", "SalePrice")


# --------------------------------------------------------------------------- #
# API routes
# --------------------------------------------------------------------------- #
from fastapi.testclient import TestClient  # noqa: E402

from analyst.api.app import create_app  # noqa: E402


def test_model_routes_full_journey(tmp_path):
    repo, name = _repo_with_ames(tmp_path)
    client = TestClient(create_app(repo))
    gallery = client.get("/api/models/gallery").json()["samples"]
    assert [g["key"] for g in gallery] == ["ames", "king_county"]

    task = client.post(
        "/api/models/tasks", json={"dataset": name, "target": "SalePrice"}
    ).json()
    assert task["status"] == "defined"
    task = client.patch(
        f"/api/models/tasks/{task['task_id']}/features",
        json={"accepted": FEATURES},
    ).json()
    task = client.post(f"/api/models/tasks/{task['task_id']}/train", json={}).json()
    assert task["status"] == "trained" and task["metrics"]["gbm"]["r2"] >= 0.80
    listed = client.get("/api/models").json()["models"]
    assert len(listed) == 1
    assert client.delete(f"/api/models/{task['task_id']}").status_code == 204


def test_model_route_errors(tmp_path):
    repo, name = _repo_with_ames(tmp_path)
    client = TestClient(create_app(repo))
    assert client.get("/api/models/nope").status_code == 404
    assert client.post("/api/models/gallery/nope").status_code == 404
    assert (
        client.post(
            "/api/models/tasks", json={"dataset": name, "target": "Nope"}
        ).status_code
        == 400
    )
    task = client.post(
        "/api/models/tasks", json={"dataset": name, "target": "SalePrice"}
    ).json()
    assert (
        client.patch(
            f"/api/models/tasks/{task['task_id']}/features",
            json={"accepted": ["SalePrice"]},
        ).status_code
        == 400
    )
    assert (
        client.post(
            f"/api/models/tasks/{task['task_id']}/train",
            json={"params": {"learning_rate": 99}},
        ).status_code
        == 400
    )


def test_predictions_ingest_never_calls_the_cataloguer(tmp_path):
    """Defect (container e2e): training 500'd in replay mode because the
    predictions ingest invoked agent cataloguing. System-generated
    prediction datasets are catalogued deterministically, never by agent."""

    class BoomCataloguer:
        def catalog(self, *a, **k):
            raise AssertionError("agent cataloguing invoked for predictions")

    repo = StoreRepository(
        str(tmp_path / "data"),
        cataloguer=BoomCataloguer(),
        model_guide=StubGuide(),
    )
    # sample ingest bypasses too? No — only predictions must; add the sample
    # with the cataloguer temporarily absent to keep this test focused.
    repo.service.cataloguer = None
    repo.add_sample("ames")
    repo.service.cataloguer = BoomCataloguer()
    task = repo.create_model_task("ames.csv", "SalePrice")
    trained = repo.train_model(task["task_id"])  # must not raise
    assert trained["status"] == "trained"
