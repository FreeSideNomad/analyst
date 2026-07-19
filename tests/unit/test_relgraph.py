"""Feature 018 — the vendored relational-graph engine, on REAL Berka data
(downloaded on demand from public mirrors into tests/.ml_cache, never in
git). The reference loop: each tier must land within ±0.03 of ITS OWN
number in the owner's paper (RESULTS.md), deterministically."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("ANALYST_ML_CACHE", "tests/.ml_cache")

from analyst.engine.relgraph import available  # noqa: E402
from analyst.engine.relgraph.pipeline import (  # noqa: E402
    DEFAULT_SEED,
    ensure_data,
    ensure_task,
    train_tiers,
)

pytestmark = pytest.mark.skipif(
    not available(), reason="ml extra (torch stack) not installed"
)

# The paper's RESULTS.md numbers for berka/loan_default.
PAPER_GRAPH_AUROC = 0.7182
PAPER_BASELINE_AUROC = 0.7647
TOLERANCE = 0.03


@pytest.fixture(scope="module")
def trained():
    ensure_data("berka")
    return train_tiers("berka", "loan_default")


def test_engine_probe_reports_available():
    assert available() is True


def test_berka_arrives_once_then_serves_from_cache():
    messages = ensure_data("berka")
    assert any("rows" in m for m in messages)
    # Second call must succeed with the network forbidden entirely.
    os.environ["RELGRAPH_OFFLINE"] = "1"
    try:
        again = ensure_data("berka")
    finally:
        del os.environ["RELGRAPH_OFFLINE"]
    assert any("already cached" in m for m in again)


def test_graph_tier_reproduces_the_paper(trained):
    auroc = trained.metrics["graph"]["test_auroc"]
    assert abs(auroc - PAPER_GRAPH_AUROC) <= TOLERANCE, (
        f"graph AUROC {auroc:.4f} outside ±{TOLERANCE} of paper {PAPER_GRAPH_AUROC}"
    )


def test_baseline_tier_reproduces_the_paper(trained):
    auroc = trained.metrics["baseline"]["test_auroc"]
    assert abs(auroc - PAPER_BASELINE_AUROC) <= TOLERANCE


def test_hybrid_is_wired_not_degraded(trained):
    hybrid = trained.metrics["hybrid"]["test_auroc"]
    stronger_parent = max(
        trained.metrics["graph"]["test_auroc"],
        trained.metrics["baseline"]["test_auroc"],
    )
    assert hybrid >= stronger_parent - 0.05


def test_training_is_deterministic(trained):
    from analyst.engine.relgraph.models import graph as graph_model
    from analyst.engine.relgraph.registry import get_spec
    from analyst.engine.relgraph.tasks import load_training_table

    spec = get_spec("berka")
    task = ensure_task("berka", "loan_default")
    frame = load_training_table("berka", "loan_default").reset_index(drop=True)
    rerun = graph_model.train_and_evaluate(
        spec, task, frame, seed=DEFAULT_SEED, smoke=False
    )
    assert rerun == trained.metrics["graph"]


def test_predictions_cover_every_loan(trained):
    p = trained.predictions
    assert len(p) == 682  # every berka loan
    assert set(p["split"].unique()) == {"train", "val", "test"}
    for col in (
        "loan_id",
        "as_of",
        "actual",
        "graph_likelihood",
        "baseline_likelihood",
        "hybrid_likelihood",
    ):
        assert col in p.columns
    assert p["actual"].isin([0, 1]).all()
    assert p["hybrid_likelihood"].between(0, 1).all()


def test_outcome_columns_never_reach_the_models(trained):
    from analyst.engine.relgraph.features import build_features
    from analyst.engine.relgraph.models.graph import _load_database
    from analyst.engine.relgraph.registry import get_spec
    from analyst.engine.relgraph.tasks import load_training_table

    spec = get_spec("berka")
    task = ensure_task("berka", "loan_default")
    assert "loan.status" in task.exclude and "loan.payments" in task.exclude
    # The baseline's feature matrix carries no outcome column.
    frame = load_training_table("berka", "loan_default").reset_index(drop=True)
    features = build_features(spec, task, frame)
    assert not any("status" in c or "payments" in c for c in features.columns)
    # The graph's database view drops them before any tensor is built.
    db = _load_database(spec, task)
    assert "status" not in db.table_dict["loan"].df.columns
    assert "payments" not in db.table_dict["loan"].df.columns


def test_task_framing_is_plain_language():
    task = ensure_task("berka", "loan_default")
    framing = task.framing
    assert framing["question"].startswith("Will this loan")
    assert "granted" in framing["moment"]
    assert "hidden" in framing["honesty"]


def test_story_names_the_relational_context(trained):
    story = trained.story
    assert story["entity_table"] == "loan"
    assert "trans" in story["tables"] and "counterparty" in story["tables"]
    assert any("loan.account_id" in e for e in story["edges"])
    assert story["split_sizes"] == {"train": 254, "val": 146, "test": 282}
    assert trained.seed == DEFAULT_SEED
    assert story["num_layers"] == 4
    assert story["excluded_outcomes"] == ["loan.payments", "loan.status"]
