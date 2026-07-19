"""Step handlers for feature 018 — relational graph (GNN) models.

Reference-data scenarios run against the REAL Berka dataset (PKDD'99),
downloaded on demand from public mirrors into tests/.ml_cache/ (gitignored)
— each tier is validated against ITS OWN number from the owner's paper
(RESULTS.md), within ±0.03, deterministic seeds. The heavy two extra
tasks' reference matrix runs with ML_FULL=1 (pre-ship + nightly); the
fast board covers loan_default end to end. The container scenario builds
and boots the analyst:ml image variant (linux/amd64 — pyg-lib ships no
arm64 linux wheel) — the owner's autonomy gate.

Training is deterministic (pinned by the unit reference loop), so the
board memoizes ONE real train_tiers run and reuses it across scenarios;
the determinism scenario itself always retrains for real.
"""

from __future__ import annotations

import atexit
import os
import subprocess
import time as _time
from pathlib import Path
from typing import Any

import httpx
import pytest

os.environ.setdefault("ANALYST_ML_CACHE", "tests/.ml_cache")

from acceptance.e2e_base import (
    _STACK,
    ScenarioContext,
    _e2e_fresh,
    _e2e_stack,
    expect_,
    make_registry,
)
from analyst.api.repository import StoreRepository
from analyst.engine import relgraph
from analyst.engine.relgraph import pipeline as _pipeline
from analyst.engine.relgraph.errors import RelgraphError

step, run_step = make_registry()
_expect = expect_
_ = _STACK  # browser steps use it; keep ruff from stripping the import

__all__ = ["ScenarioContext", "run_step", "_e2e_stack", "_e2e_fresh"]

REPO_ROOT = Path(__file__).resolve().parent.parent

# Deterministic-training memo: one real run feeds every scenario that
# needs "a trained model"; determinism is separately proven by retraining.
_REAL_TRAIN_TIERS = _pipeline.train_tiers
_TRAIN_MEMO: dict = {}


def _memo_train_tiers(dataset: str, task: str, seed: int = _pipeline.DEFAULT_SEED):
    key = (dataset, task, seed)
    if key not in _TRAIN_MEMO:
        _TRAIN_MEMO[key] = _REAL_TRAIN_TIERS(dataset, task, seed=seed)
    return _TRAIN_MEMO[key]


_pipeline.train_tiers = _memo_train_tiers

PAPER = {  # RESULTS.md — each tier validated against its own number
    ("loan_default", "graph"): 0.7182,
    ("loan_default", "baseline"): 0.7647,
    ("account_churn", "graph"): 0.7592,
    ("account_churn", "baseline"): 0.9018,
    ("card_adoption", "graph"): 0.6787,
    ("card_adoption", "baseline"): 0.7999,
}


def _state(ctx: ScenarioContext) -> dict[str, Any]:
    if not isinstance(ctx.data, dict):
        ctx.data = {}
    return ctx.data


def _repo(ctx: ScenarioContext) -> StoreRepository:
    state = _state(ctx)
    if "repo" not in state:
        state["repo"] = StoreRepository(str(ctx.tmp_path / "data"))
    return state["repo"]


def _task(ctx: ScenarioContext) -> dict:
    state = _state(ctx)
    return state["repo"].model(state["task_id"])


# --------------------------------------------------------------------------- #
# Givens
# --------------------------------------------------------------------------- #
@step(r"the sample gallery is available")
def given_gallery(ctx: ScenarioContext) -> None:
    bundle = _repo(ctx).relational_bundle()
    assert bundle["key"] == "berka" and bundle["available"]


@step(r"the Berka bundle is in the workspace")
def given_bundle(ctx: ScenarioContext) -> None:
    _repo(ctx).add_relational_bundle()


@step(r"a workspace whose tables have no validated links")
def given_bare_workspace(ctx: ScenarioContext) -> None:
    _repo(ctx)  # fresh store: nothing ingested, no links, no dates


@step(r"the loan default task is defined")
def given_task_defined(ctx: ScenarioContext) -> None:
    given_bundle(ctx)
    task = _repo(ctx).create_relational_task("loan_default")
    _state(ctx)["task_id"] = task["task_id"]


@step(r'the Berka task "(?P<name>[^"]+)" is defined')
def given_named_task(ctx: ScenarioContext, name: str) -> None:
    if os.environ.get("ML_FULL") != "1":
        pytest.skip(
            f"full reference matrix ({name}) runs with ML_FULL=1 "
            "(pre-ship + nightly gate)"
        )
    given_bundle(ctx)
    task = _repo(ctx).create_relational_task(name)
    _state(ctx)["task_id"] = task["task_id"]
    _state(ctx)["task_name"] = name


@step(r"training will fail partway through")
def given_training_fails(ctx: ScenarioContext) -> None:
    def _boom(dataset: str, task: str, seed: int = 0):
        raise RelgraphError("the training data vanished mid-run")

    _pipeline.train_tiers = _boom
    _state(ctx)["patched"] = True


@step(r"a trained loan default model")
def given_trained(ctx: ScenarioContext) -> None:
    given_task_defined(ctx)
    state = _state(ctx)
    state["task"] = state["repo"].train_relational(state["task_id"])


@step(r"the app runs without the ML runtime")
def given_no_ml_runtime(ctx: ScenarioContext) -> None:
    _repo(ctx)
    _state(ctx)["real_available"] = relgraph.available
    relgraph.available = lambda: False


# --------------------------------------------------------------------------- #
# Whens
# --------------------------------------------------------------------------- #
@step(r"the user adds the Berka banking dataset")
def when_add_bundle(ctx: ScenarioContext) -> None:
    _state(ctx)["added"] = _repo(ctx).add_relational_bundle()


@step(r"the user starts the loan default prediction task")
def when_start_task(ctx: ScenarioContext) -> None:
    task = _repo(ctx).create_relational_task("loan_default")
    _state(ctx)["task_id"] = task["task_id"]


@step(r"the user asks for a relational model there")
def when_ask_unsuitable(ctx: ScenarioContext) -> None:
    try:
        _repo(ctx).create_relational_task("loan_default")
        raise AssertionError("expected a refusal")
    except ValueError as exc:
        _state(ctx)["error"] = exc


@step(r"the graph model is trained twice with the same seed")
def when_train_twice(ctx: ScenarioContext) -> None:
    from analyst.engine.relgraph.models import graph as graph_model
    from analyst.engine.relgraph.registry import get_spec
    from analyst.engine.relgraph.tasks import load_training_table

    spec = get_spec("berka")
    task_spec = _pipeline.ensure_task("berka", "loan_default")
    frame = load_training_table("berka", "loan_default").reset_index(drop=True)
    runs = [
        graph_model.train_and_evaluate(
            spec, task_spec, frame, seed=_pipeline.DEFAULT_SEED, smoke=False
        )
        for _ in range(2)
    ]
    _state(ctx)["runs"] = runs


@step(r'the graph model and the baseline are trained for "(?P<name>[^"]+)"')
def when_train_named(ctx: ScenarioContext, name: str) -> None:
    state = _state(ctx)
    state["task"] = state["repo"].train_relational(state["task_id"])
    state["task_name"] = name


@step(r"the graph model and the baseline are trained")
def when_train_tiers(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    state["task"] = state["repo"].train_relational(state["task_id"])
    state["task_name"] = "loan_default"


@step(r"the hybrid model is trained on the same split")
def when_train_hybrid(ctx: ScenarioContext) -> None:
    when_train_tiers(ctx)


@step(r"the graph model is trained")
def when_train_once(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    try:
        state["task"] = state["repo"].train_relational(state["task_id"])
    except RelgraphError as exc:
        state["error"] = exc
    finally:
        if state.pop("patched", None):
            _pipeline.train_tiers = _memo_train_tiers


@step(r"the app restarts")
def when_restart(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    state["repo"] = StoreRepository(str(ctx.tmp_path / "data"))


# --------------------------------------------------------------------------- #
# Thens
# --------------------------------------------------------------------------- #
@step(r"the Berka tables are profiled and queryable with their links validated")
def then_tables_ready(ctx: ScenarioContext) -> None:
    repo = _repo(ctx)
    names = {r for r in repo._records}
    for table in ("berka_loan.csv", "berka_account.csv", "berka_trans.csv"):
        assert table in names
        record = repo._records[table]
        assert record.summary.profile.columns  # profiled
    frame = repo.store.fetch_frame("berka_loan.csv")
    assert len(frame) == 682  # queryable, every loan
    assert repo.store.discover_relationships()  # validated links exist


@step(r"adding Berka again uses the local cache without downloading")
def then_cached_readd(ctx: ScenarioContext) -> None:
    os.environ["RELGRAPH_OFFLINE"] = "1"
    try:
        again = _repo(ctx).add_relational_bundle()
    finally:
        del os.environ["RELGRAPH_OFFLINE"]
    assert len(again["tables"]) == len(_state(ctx)["added"]["tables"])


@step(r"the task is framed as a decision in plain language")
def then_framed(ctx: ScenarioContext) -> None:
    framing = _task(ctx)["framing"]
    assert framing["question"] == "Will this loan end in default?"
    assert "granted" in framing["moment"]
    assert "hidden" in framing["honesty"]


@step(r"the columns that record the outcome are named and excluded")
def then_outcomes_named(ctx: ScenarioContext) -> None:
    assert _task(ctx)["excluded_outcomes"] == ["loan.payments", "loan.status"]


@step(r"the request is refused before training with the missing prerequisites named")
def then_refused(ctx: ScenarioContext) -> None:
    error = str(_state(ctx)["error"])
    assert "validated links" in error and "date column" in error
    assert not _repo(ctx).models()  # nothing was created


@step(r"any guidance exchange carries schema and catalog metadata only")
def then_no_exchange_needed(ctx: ScenarioContext) -> None:
    # Stronger than the AC asks: the relational flow performs ZERO agent
    # exchanges — the framing is authored task metadata (the repo has no
    # guide at all and the task still framed itself).
    assert _repo(ctx).model_guide is None
    assert _task(ctx)["framing"]["question"]


@step(r"the exchange carries no account, transaction or client records")
def then_no_records(ctx: ScenarioContext) -> None:
    import json

    payload = json.dumps(_task(ctx))
    frame = _repo(ctx).store.fetch_frame("berka_trans.csv")
    sample_ids = {str(v) for v in frame["trans_id"].head(50)}
    assert not any(tid in payload for tid in sample_ids)


@step(r"both runs report identical evaluation scores")
def then_identical(ctx: ScenarioContext) -> None:
    first, second = _state(ctx)["runs"]
    assert first == second


@step(
    r"the graph model's held-out score is within 0.03 of (?:the paper's )?\"?(?P<ref>[0-9.]+)\"?"
)
def then_graph_reference(ctx: ScenarioContext, ref: str) -> None:
    state = _state(ctx)
    auroc = state["task"]["metrics"]["graph"]["test_auroc"]
    expected = PAPER[(state["task_name"], "graph")]
    assert abs(float(ref) - expected) < 1e-9  # spec and RESULTS.md agree
    assert abs(auroc - expected) <= 0.03, f"graph {auroc:.4f} vs paper {expected}"


@step(
    r"the baseline's held-out score is within 0.03 of (?:the paper's )?\"?(?P<ref>[0-9.]+)\"?"
)
def then_baseline_reference(ctx: ScenarioContext, ref: str) -> None:
    state = _state(ctx)
    auroc = state["task"]["metrics"]["baseline"]["test_auroc"]
    expected = PAPER[(state["task_name"], "baseline")]
    assert abs(float(ref) - expected) < 1e-9
    assert abs(auroc - expected) <= 0.03, f"baseline {auroc:.4f} vs paper {expected}"


@step(r"the comparison between tiers is reported truthfully")
def then_truthful_comparison(ctx: ScenarioContext) -> None:
    task = _state(ctx)["task"]
    m = task["metrics"]
    text = task["evaluation"]
    assert f"{m['baseline']['test_auroc']:.2f}" in text
    assert f"{m['graph']['test_auroc']:.2f}" in text
    # The paper's finding stands: when the simple tier wins, the sentence
    # must not crown the graph.
    if m["baseline"]["test_auroc"] > max(
        m["graph"]["test_auroc"], m["hybrid"]["test_auroc"]
    ):
        assert "simple approach reads the risk best" in text


@step(r"the hybrid's held-out score is reported alongside both parents")
def then_hybrid_reported(ctx: ScenarioContext) -> None:
    m = _state(ctx)["task"]["metrics"]
    assert set(m) == {"graph", "baseline", "hybrid"}
    assert 0 < m["hybrid"]["test_auroc"] <= 1


@step(r"the hybrid scores no more than 0.05 below the stronger parent")
def then_hybrid_guard(ctx: ScenarioContext) -> None:
    m = _state(ctx)["task"]["metrics"]
    stronger = max(m["graph"]["test_auroc"], m["baseline"]["test_auroc"])
    assert m["hybrid"]["test_auroc"] >= stronger - 0.05


@step(r"the failure is reported plainly")
def then_failure_plain(ctx: ScenarioContext) -> None:
    assert "vanished" in str(_state(ctx)["error"])


@step(r"the registry contains no partial model")
def then_no_partial(ctx: ScenarioContext) -> None:
    task = _task(ctx)
    assert task["status"] == "defined"
    assert task["metrics"] is None and task["predictions_dataset"] is None


@step(r"a predictions dataset exists with one row per loan")
def then_predictions_exist(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    name = state["task"]["predictions_dataset"]
    assert name in state["repo"]._records
    assert len(state["repo"].store.fetch_frame(name)) == 682


@step(
    r"each row carries the actual outcome, the predicted likelihood "
    r"and the holdout flag"
)
def then_prediction_columns(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    frame = state["repo"].store.fetch_frame(state["task"]["predictions_dataset"])
    for col in ("actual", "hybrid_likelihood", "split"):
        assert col in frame.columns
    assert set(frame["split"].unique()) == {"train", "val", "test"}


@step(r"the predictions dataset is queryable like any other")
def then_predictions_queryable(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    frame = state["repo"].store.fetch_frame(state["task"]["predictions_dataset"])
    assert frame["actual"].isin([0, 1]).all()


@step(
    r"the registry names the task, the tables and links learned from, "
    r"the time split, the seed and the set sizes"
)
def then_registry_story(ctx: ScenarioContext) -> None:
    task = _task(ctx)
    story = task["story"]
    assert task["task"] == "loan_default"
    assert "trans" in story["tables"] and story["edges"]
    assert "by time" in story["split"]
    assert task["seed"] == _pipeline.DEFAULT_SEED
    assert story["split_sizes"] == {"train": 254, "val": 146, "test": 282}


@step(r"every tier's score is stated in plain language")
def then_scores_plain(ctx: ScenarioContext) -> None:
    text = _task(ctx)["evaluation"]
    assert "simple approach" in text and "graph approach" in text
    assert "coin flip" in text


@step(r"the registry still lists the relational model with its story")
def then_registry_survives(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    task = state["repo"].model(state["task_id"])
    assert task["status"] == "trained" and task["story"]["tables"]


@step(r"the predictions dataset is still queryable")
def then_predictions_survive(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    task = state["repo"].model(state["task_id"])
    frame = state["repo"].store.fetch_frame(task["predictions_dataset"])
    assert len(frame) == 682


@step(r"the relational tier explains plainly that the ML variant is needed")
def then_lean_explains(ctx: ScenarioContext) -> None:
    try:
        bundle = _repo(ctx).relational_bundle()
        assert bundle["available"] is False
        assert "analyst:ml" in bundle["message"]
        try:
            _repo(ctx).create_relational_task("loan_default")
            raise AssertionError("expected a refusal")
        except ValueError as exc:
            assert "analyst:ml" in str(exc)
    finally:
        relgraph.available = _state(ctx)["real_available"]


@step(r"single-table models keep working")
def then_single_table_works(ctx: ScenarioContext) -> None:
    repo = _repo(ctx)
    assert [s.key for s in repo.model_gallery()] == ["ames", "king_county"]
    record = repo.add_sample("ames")  # cached CSV, offline, no agent
    assert record.summary.profile.columns


# --------------------------------------------------------------------------- #
# AC-14 — the deployed analyst:ml container (the owner's autonomy gate).
# --------------------------------------------------------------------------- #

_CONTAINER = "analyst-ml-container-e2e"


def _docker_cleanup() -> None:
    subprocess.run(["docker", "rm", "-f", _CONTAINER], capture_output=True)


@step(r"the analyst ML container is built and running in replay mode")
def given_ml_container(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    _docker_cleanup()
    atexit.register(_docker_cleanup)
    build = subprocess.run(
        [
            "docker",
            "build",
            "-q",
            "--platform",
            "linux/amd64",  # pyg-lib has no linux/arm64 wheel
            "--target",
            "ml",
            "-t",
            "analyst:e2e-ml",
            str(REPO_ROOT),
        ],
        capture_output=True,
        text=True,
        timeout=1800,
    )
    assert build.returncode == 0, build.stderr[-800:]
    import socket

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    run = subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--platform",
            "linux/amd64",
            "--name",
            _CONTAINER,
            "-p",
            f"{port}:8000",
            "-v",
            f"{REPO_ROOT}/tests/cassettes:/cassettes:ro",
            "-v",
            f"{REPO_ROOT}/tests/.ml_cache:/mlcache:ro",
            "-e",
            "ANALYST_CATALOG_CASSETTE=/cassettes/models_guidance.json",
            "-e",
            "ANALYST_ML_CACHE=/mlcache",
            "analyst:e2e-ml",
        ],
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stderr[-500:]
    url = f"http://127.0.0.1:{port}"
    deadline = _time.monotonic() + 300  # emulated boot is slow on arm hosts
    while _time.monotonic() < deadline:
        try:
            if httpx.get(f"{url}/api/health", timeout=2).status_code == 200:
                break
        except Exception:  # noqa: BLE001 - booting
            _time.sleep(2)
    else:
        raise AssertionError("ml container did not become healthy")
    state["container_url"] = url
    state["container_page"] = _STACK["browser"].new_page(
        viewport={"width": 1440, "height": 900}
    )


@step(r"the user completes the relational model journey in a browser")
def when_ml_journey(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    page = state["container_page"]
    expect = _expect()
    page.goto(state["container_url"])
    page.get_by_role("button", name="Models", exact=True).click()
    page.get_by_label("Add bundle Berka bank (relational)").click()
    # nine real tables (1M+ transaction rows) through the normal pipeline
    deadline = _time.monotonic() + 600
    while _time.monotonic() < deadline:
        datasets = httpx.get(
            f"{state['container_url']}/api/datasets", timeout=10
        ).json()
        if any(d["name"] == "berka_loan.csv" for d in datasets):
            break
        _time.sleep(3)
    page.get_by_label("Relational task").select_option("loan_default")
    page.get_by_label("Start relational model").click()
    expect(page.get_by_label("Task framing")).to_be_visible(timeout=120000)
    expect(page.get_by_label("Excluded outcomes")).to_be_visible()
    page.get_by_label("Train relational model").click()
    # graph + baseline + hybrid, emulated on arm hosts — generous budget
    expect(page.get_by_label("Relational evaluation")).to_be_visible(timeout=900000)
    expect(page.get_by_label("Relational story")).to_be_visible()


@step(r"the loan predictions dataset is visible in the deployed app")
def then_ml_predictions(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    expect = _expect()
    expect(
        state["container_page"].get_by_label("Predictions dataset", exact=False)
    ).to_be_visible()
    datasets = httpx.get(f"{state['container_url']}/api/datasets", timeout=10).json()
    predictions = [d for d in datasets if "predictions" in d["name"]]
    assert predictions and predictions[0]["rowCount"] == 682


@step(r"the relational model's story is shown in its registry card")
def then_ml_registry(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    page = state["container_page"]
    expect = _expect()
    page.get_by_label("Back to models").click()
    expect(page.get_by_label("metrics", exact=False).first).to_be_visible()
    expect(page.get_by_text("graph", exact=False).first).to_be_visible()
    page.close()
    _docker_cleanup()
