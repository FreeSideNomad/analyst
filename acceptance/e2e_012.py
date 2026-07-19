"""Step handlers for feature 012 — guided predictive models (MVP).

Realistic-data scenarios run against the REAL Ames dataset, downloaded on
demand into tests/.ml_cache/ (gitignored, like the golden corpus) — the
owner's directive: the acceptance loop iterates against real data until
green. Agent turns replay tests/cassettes/models_guidance.json. The
container scenario builds and boots the actual Docker image in replay mode
and drives it with Playwright (skippable with CONTAINER_E2E=0; on by
default — it is the owner's autonomy condition).

Bindings land per slice; unbound steps fail NOT YET IMPLEMENTED.
"""

from __future__ import annotations

import atexit
import os
import subprocess
import time as _time
from pathlib import Path
from typing import Any

import httpx

os.environ.setdefault("ANALYST_ML_CACHE", "tests/.ml_cache")

from acceptance.e2e_base import (
    _STACK,
    ScenarioContext,
    _e2e_fresh,
    _e2e_stack,
    expect_,
    make_registry,
)
from analyst.agentic.gateway import LLMGateway, LLMRequest, ReplayBackend
from analyst.agentic.models import ModelGuidanceError, ModelGuide
from analyst.api.repository import StoreRepository
from analyst.domain.models import UnknownModelError
from analyst.engine.mltrain import LeakageError

step, run_step = make_registry()
_expect = expect_
_ = _STACK  # browser steps use it; keep ruff from stripping the import

__all__ = ["ScenarioContext", "run_step", "_e2e_stack", "_e2e_fresh"]


REPO_ROOT = Path(__file__).resolve().parent.parent
GUIDANCE_CASSETTE = str(REPO_ROOT / "tests" / "cassettes" / "models_guidance.json")


class _SpyBackend:
    def __init__(self, inner: ReplayBackend, log: list):
        self.inner, self.log = inner, log

    def complete(self, request: LLMRequest) -> str:
        self.log.append(request)
        return self.inner.complete(request)


def _state(ctx: ScenarioContext) -> dict[str, Any]:
    if not isinstance(ctx.data, dict):
        ctx.data = {"exchanges": []}
    return ctx.data


def _guide(ctx: ScenarioContext) -> ModelGuide:
    return ModelGuide(
        LLMGateway(
            _SpyBackend(ReplayBackend(GUIDANCE_CASSETTE), _state(ctx)["exchanges"])
        )
    )


def _repo(ctx: ScenarioContext) -> StoreRepository:
    state = _state(ctx)
    if "repo" not in state:
        state["repo"] = StoreRepository(
            str(ctx.tmp_path / "data"), model_guide=_guide(ctx)
        )
    return state["repo"]


def _task(ctx: ScenarioContext) -> dict:
    state = _state(ctx)
    return state["repo"].model(state["task_id"])


# --------------------------------------------------------------------------- #
# Givens
# --------------------------------------------------------------------------- #
@step(r"the sample gallery is available")
def given_gallery(ctx: ScenarioContext) -> None:
    assert [s.key for s in _repo(ctx).model_gallery()] == ["ames", "king_county"]


@step(r"the Ames dataset is in the workspace")
def given_ames(ctx: ScenarioContext) -> None:
    record = _repo(ctx).add_sample("ames")
    _state(ctx)["dataset"] = record.name


@step(r"the guidance will fail on the next attempt")
def given_failing_guide(ctx: ScenarioContext) -> None:
    class _Boom:
        def guide(self, table: Any, target: str) -> Any:
            raise ModelGuidanceError("guidance failed")

    _repo(ctx).model_guide = _Boom()


@step(r"a defined SalePrice task with accepted features")
def given_defined_task(ctx: ScenarioContext) -> None:
    given_ames(ctx)
    state = _state(ctx)
    task = state["repo"].create_model_task(state["dataset"], "SalePrice")
    state["task_id"] = task["task_id"]


@step(r"a trained SalePrice model")
def given_trained_model(ctx: ScenarioContext) -> None:
    given_defined_task(ctx)
    state = _state(ctx)
    state["repo"].train_model(state["task_id"])


@step(r"the app runs offline with no AI features available")
def given_offline(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    state["repo"] = StoreRepository(str(ctx.tmp_path / "data"))  # no guide


# --------------------------------------------------------------------------- #
# Whens
# --------------------------------------------------------------------------- #
@step(r"the user adds the Ames house-price dataset")
def when_add_ames(ctx: ScenarioContext) -> None:
    record = _repo(ctx).add_sample("ames")
    _state(ctx)["dataset"] = record.name


@step(r'the user starts a new model to predict "SalePrice"')
def when_start_model(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    try:
        task = state["repo"].create_model_task(state["dataset"], "SalePrice")
        state["task_id"], state["error"] = task["task_id"], None
    except ModelGuidanceError as exc:
        state["error"] = exc


@step(r"the user removes one proposed feature and accepts the rest")
def when_curate_features(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    task = _task(ctx)
    keep = [f["name"] for f in task["proposed"]][:-1]
    state["repo"].update_task_features(state["task_id"], keep)
    state["accepted"] = keep


@step(r"the model is trained twice")
def when_train_twice(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    first = dict(state["repo"].train_model(state["task_id"])["metrics"])
    second = dict(state["repo"].train_model(state["task_id"])["metrics"])
    state["runs"] = (first, second)


@step(r"the model is trained(?: with default parameters)?")
def when_train(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    state["repo"].train_model(state["task_id"])


@step(r'the user tries to add "SalePrice" itself as a feature')
def when_add_target_as_feature(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    task = _task(ctx)
    try:
        state["repo"].update_task_features(
            state["task_id"], task["accepted"] + ["SalePrice"]
        )
        state["error"] = None
    except LeakageError as exc:
        state["error"] = exc


@step(r"a parameter outside its allowed bounds is submitted")
def when_bad_param(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    try:
        state["repo"].train_model(state["task_id"], {"learning_rate": 9.0})
        state["error"] = None
    except ValueError as exc:
        state["error"] = exc


@step(r"the app restarts")
def when_restart(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    state["repo"] = StoreRepository(str(ctx.tmp_path / "data"))


@step(r"the user opens a model that does not exist")
def when_open_missing_model(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    try:
        state["repo"].model("no-such-model")
        state["error"] = None
    except UnknownModelError as exc:
        state["error"] = exc


@step(r"an empty feature selection is submitted")
def when_empty_features(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    try:
        state["repo"].update_task_features(state["task_id"], [])
        state["error"] = None
    except ValueError as exc:
        state["error"] = exc


# --------------------------------------------------------------------------- #
# Thens
# --------------------------------------------------------------------------- #
@step(r"a dataset of 1460 homes with 81 columns is profiled and queryable")
def then_ames_profiled(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    record = state["repo"].get_dataset(state["dataset"])
    assert record.summary.profile.row_count == 1460
    assert len(record.summary.profile.columns) == 81
    counts = state["repo"].store.value_counts(state["dataset"], "CentralAir")
    assert counts.get("Y", 0) > 1000


@step(r"adding it again uses the local cache without downloading")
def then_cached_readd(ctx: ScenarioContext) -> None:
    import analyst.engine.mlsamples as mlsamples
    from sklearn import datasets as skdatasets

    def _no_network(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("network download attempted despite cache")

    original = skdatasets.fetch_openml
    skdatasets.fetch_openml = _no_network  # type: ignore[assignment]
    try:
        again = _state(ctx)["repo"].add_sample("ames")
        assert again.name == _state(ctx)["dataset"]
        assert mlsamples.fetch_sample_csv("ames").is_file()
    finally:
        skdatasets.fetch_openml = original  # type: ignore[assignment]


@step(r"a regression task is saved with a held-out fifth of the homes")
def then_task_saved(ctx: ScenarioContext) -> None:
    task = _task(ctx)
    assert task["task_type"] == "regression" and task["status"] == "defined"
    assert "fifth" in task["split_note"] or "20%" in task["split_note"]


@step(r"the split was presented as a decision in plain language")
def then_split_is_decision(ctx: ScenarioContext) -> None:
    note = _task(ctx)["split_note"].lower()
    assert "you" in note and ("hide" in note or "hold" in note or "set aside" in note)


@step(r"the agent proposes features each with a plain-language reason")
def then_features_proposed(ctx: ScenarioContext) -> None:
    task = _task(ctx)
    assert 10 <= len(task["proposed"]) <= 18
    assert all(f["reason"].strip() for f in task["proposed"])
    assert all(f["name"] != "SalePrice" for f in task["proposed"])


@step(r"the accepted features materialize as a queryable feature table")
def then_feature_table(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    frame = state["repo"].store.fetch_frame(f"{state['task_id']}.features")
    assert list(frame.columns) == state["accepted"]
    assert len(frame) == 1460


@step(r"the exchange sent for guidance carries schema and catalog metadata")
def then_exchange_metadata(ctx: ScenarioContext) -> None:
    (request,) = _state(ctx)["exchanges"]
    assert "SalePrice" in request.prompt and "Columns:" in request.prompt


@step(r"the exchange carries no home records")
def then_exchange_no_rows(ctx: ScenarioContext) -> None:
    (request,) = _state(ctx)["exchanges"]
    # a raw Ames CSV row would carry many comma-separated fields; the prompt
    # carries per-column metadata lines instead
    assert "RL,65" not in request.prompt and ",WD,Normal," not in request.prompt


@step(r"the failure is reported plainly")
def then_failure_plain(ctx: ScenarioContext) -> None:
    assert isinstance(_state(ctx)["error"], ModelGuidanceError)


@step(r"no task and no model exist afterwards")
def then_nothing_created(ctx: ScenarioContext) -> None:
    assert _state(ctx)["repo"].models() == []


@step(r"both runs report identical metrics")
def then_deterministic(ctx: ScenarioContext) -> None:
    first, second = _state(ctx)["runs"]
    assert first == second


@step(r"the upgraded model's holdout fit is at least 0.80")
def then_threshold(ctx: ScenarioContext) -> None:
    r2 = _task(ctx)["metrics"]["gbm"]["r2"]
    # upper bound guards the holdout-leak mutation: training on the holdout
    # would inflate this towards a memorized ~0.98
    assert 0.80 <= r2 <= 0.95, r2


@step(r"the upgraded model beats the simple baseline")
def then_beats_baseline(ctx: ScenarioContext) -> None:
    metrics = _task(ctx)["metrics"]
    assert metrics["gbm"]["mae"] < metrics["linear"]["mae"]


@step(r"the evaluation says in dollars how far off a typical prediction is")
def then_evaluation_dollars(ctx: ScenarioContext) -> None:
    evaluation = _task(ctx)["evaluation"]
    assert "$" in evaluation and "held-out" in evaluation


@step(r"the addition is rejected with an explanation")
def then_leak_rejected(ctx: ScenarioContext) -> None:
    error = _state(ctx)["error"]
    assert isinstance(error, LeakageError) and "predicted" in str(error)


@step(r"the held-out homes never influenced training")
def then_holdout_untouched(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    if _task(ctx)["status"] != "trained":
        state["repo"].train_model(state["task_id"])
    task = _task(ctx)
    assert task["holdout_count"] == 292
    # the window guards the holdout-leak mutation: training on the holdout
    # inflates the score towards memorization
    assert 0.80 <= task["metrics"]["gbm"]["r2"] <= 0.95


@step(r"training succeeds without any parameter being touched")
def then_defaults_trained(ctx: ScenarioContext) -> None:
    task = _task(ctx)
    assert task["status"] == "trained" and task["params"]["n_estimators"] == 400


@step(r"the submission is rejected with the allowed range")
def then_param_rejected(ctx: ScenarioContext) -> None:
    error = _state(ctx)["error"]
    assert isinstance(error, ValueError) and "between" in str(error)


@step(r"a predictions dataset exists with one row per home")
def then_predictions_exist(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    name = _task(ctx)["predictions_dataset"]
    record = state["repo"].get_dataset(name)
    assert record is not None and record.summary.profile.row_count == 1460
    state["predictions"] = name


@step(r"each row carries the actual price, the predicted price and the model version")
def then_prediction_columns(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    record = state["repo"].get_dataset(state["predictions"])
    names = {c.name for c in record.summary.profile.columns}
    assert {"actual", "predicted", "model"} <= names


@step(r"the predictions dataset is queryable like any other")
def then_predictions_queryable(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    counts = state["repo"].store.value_counts(state["predictions"], "model")
    assert sum(counts.values()) == 1460


@step(r"the registry lists its data, features, split, seed and metrics")
def then_registry_story(ctx: ScenarioContext) -> None:
    (task,) = _state(ctx)["repo"].models()
    assert task["dataset"] and task["accepted"]
    assert task["params"]["seed"] == 42 and task["params"]["holdout"] == 0.2
    assert task["metrics"]["gbm"]["r2"] > 0


@step(r"the most influential features are named in plain language")
def then_importances_plain(ctx: ScenarioContext) -> None:
    task = _task(ctx)
    names = [n for n, _ in task["importances"]]
    assert names and all("__" not in n and n in task["accepted"] for n in names)


@step(r"the registry still lists the model with its metrics")
def then_registry_survives(ctx: ScenarioContext) -> None:
    (task,) = _state(ctx)["repo"].models()
    _state(ctx)["task_id"] = task["task_id"]
    assert task["status"] == "trained" and task["metrics"]["gbm"]["r2"] >= 0.80


@step(r"the predictions dataset is still queryable")
def then_predictions_survive(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    name = _task(ctx)["predictions_dataset"]
    counts = state["repo"].store.value_counts(name, "model")
    assert sum(counts.values()) == 1460


@step(r"the registry and the predictions dataset still work")
def then_offline_registry(ctx: ScenarioContext) -> None:
    then_registry_survives(ctx)
    then_predictions_survive(ctx)


@step(r"starting a new model fails with a plain message")
def then_offline_create_fails(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    try:
        state["repo"].create_model_task("ames.csv", "SalePrice")
        raise AssertionError("expected ModelGuidanceError")
    except ModelGuidanceError as exc:
        assert "AI" in str(exc)


@step(r"the action is rejected as not found")
def then_not_found(ctx: ScenarioContext) -> None:
    assert isinstance(_state(ctx)["error"], UnknownModelError)


@step(r"it is rejected with a message")
def then_rejected_message(ctx: ScenarioContext) -> None:
    assert isinstance(_state(ctx)["error"], ValueError)


# --------------------------------------------------------------------------- #
# AC-13 — the deployed-container journey (the owner's autonomy condition).
# Builds the real image, runs it in full replay mode with the pre-warmed ML
# cache mounted, and drives the whole journey with Playwright.
# --------------------------------------------------------------------------- #

_CONTAINER = "analyst-container-e2e"


def _docker_cleanup() -> None:
    subprocess.run(["docker", "rm", "-f", _CONTAINER], capture_output=True)


@step(r"the analyst container is built and running in replay mode")
def given_container_running(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    _docker_cleanup()
    atexit.register(_docker_cleanup)
    build = subprocess.run(
        ["docker", "build", "-q", "-t", "analyst:e2e", str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=900,
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
            "analyst:e2e",
        ],
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stderr[-500:]
    url = f"http://127.0.0.1:{port}"
    deadline = _time.monotonic() + 120
    while _time.monotonic() < deadline:
        try:
            if httpx.get(f"{url}/api/health", timeout=2).status_code == 200:
                break
        except Exception:  # noqa: BLE001 - booting
            _time.sleep(1)
    else:
        raise AssertionError("container did not become healthy")
    state["container_url"] = url
    state["container_page"] = _STACK["browser"].new_page(
        viewport={"width": 1440, "height": 900}
    )


@step(r"the user completes the model journey in a browser")
def when_container_journey(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    page = state["container_page"]
    expect = _expect()
    page.goto(state["container_url"])
    page.get_by_role("button", name="Models", exact=True).click()
    page.get_by_label("Add sample Ames house prices").click()
    # real 1,460-row ingest + replayed cataloguing inside the container
    deadline = _time.monotonic() + 120
    while _time.monotonic() < deadline:
        datasets = httpx.get(f"{state['container_url']}/api/datasets", timeout=5).json()
        if any(d["name"] == "ames.csv" for d in datasets):
            break
        _time.sleep(2)
    page.get_by_label("Model dataset").select_option("ames.csv")
    page.get_by_label("Model target").select_option("SalePrice")
    page.get_by_label("Start model").click()
    expect(page.get_by_label("Teaching note")).to_be_visible(timeout=60000)
    expect(page.get_by_label("Split note")).to_be_visible()
    page.get_by_label("Accept features and train").click()
    expect(page.get_by_label("Model evaluation")).to_be_visible(timeout=180000)
    expect(page.get_by_text("Trained model", exact=False).first).to_be_visible()


@step(r"the predictions dataset is visible in the deployed app")
def then_container_predictions(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    expect = _expect()
    expect(
        state["container_page"].get_by_label("Predictions dataset", exact=False)
    ).to_be_visible()
    datasets = httpx.get(f"{state['container_url']}/api/datasets", timeout=10).json()
    predictions = [d for d in datasets if "predictions" in d["name"]]
    assert predictions and predictions[0]["rowCount"] == 1460


@step(r"the model's metrics are shown in its registry card")
def then_container_registry(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    page = state["container_page"]
    expect = _expect()
    page.get_by_label("Back to models").click()
    expect(page.get_by_label("metrics", exact=False).first).to_be_visible()
    expect(page.get_by_text("typical miss $", exact=False).first).to_be_visible()
    page.close()
    _docker_cleanup()
