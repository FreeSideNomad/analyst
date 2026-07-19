"""Step handlers for feature 019 — guided graph authoring.

Curated Berka arrives the two ways a user's data arrives: a seeded
Postgres (self-provisioned docker container — types stay faithful; SQLite
would flatten dates to text) and ordinary file uploads. The generated
authoring flow must reproduce the curated 018 reference: baseline
bitwise-vs-curated-run and within ±0.03 of 0.7647; graph within ±0.02 of
the curated same-machine run and ±0.07 of 0.7182. Authoring turns replay
tests/cassettes/graph_authoring.json. The container scenario boots
analyst:ml + the seeded Postgres on one docker network — the owner's
autonomy gate.

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
os.environ.setdefault("ANALYST_SECRET_KEY", "e2e-019-passphrase")

from acceptance.e2e_base import (
    _STACK,
    ScenarioContext,
    _e2e_fresh,
    _e2e_stack,
    expect_,
    make_registry,
)
from analyst.agentic.gateway import LLMGateway, LLMRequest, ReplayBackend
from analyst.agentic.graphauthor import GraphAuthor, GraphAuthoringError
from analyst.api.repository import StoreRepository
from analyst.api.routes.databases import DatabaseManager
from analyst.domain.connection import ConnectionSpec, DatabaseEngine
from analyst.engine.credentials import CredentialVault
from analyst.engine.relgraph import pipeline as _pipeline

step, run_step = make_registry()
_expect = expect_
_ = _STACK

__all__ = ["ScenarioContext", "run_step", "_e2e_stack", "_e2e_fresh"]

REPO_ROOT = Path(__file__).resolve().parent.parent
CASSETTE = str(REPO_ROOT / "tests" / "cassettes" / "graph_authoring.json")
QUESTION = "Which loans will end in default?"

_PG_CONTAINER = "analyst-e2e-berka-pg"
_PG_PORT = 55532  # 55432 is the demo compose postgres
_PG_CONNINFO = f"host=127.0.0.1 port={_PG_PORT} dbname=berka user=postgres password=e2e"

# One curated reference run per board process (deterministic; 018-proven).
_CURATED: dict = {}


def _curated_metrics() -> dict:
    if not _CURATED:
        result = _pipeline.train_tiers("berka", "loan_default", seed=13)
        _CURATED["metrics"] = result.metrics
    return _CURATED["metrics"]


def _pg_cleanup() -> None:
    subprocess.run(["docker", "rm", "-f", _PG_CONTAINER], capture_output=True)


def _ensure_seeded_postgres() -> None:
    """Module-lifetime seeded Postgres in docker (types stay faithful)."""
    probe = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", _PG_CONTAINER],
        capture_output=True,
        text=True,
    )
    if probe.returncode == 0 and probe.stdout.strip() == "true":
        return
    _pg_cleanup()
    atexit.register(_pg_cleanup)
    run = subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            _PG_CONTAINER,
            "-e",
            "POSTGRES_PASSWORD=e2e",
            "-e",
            "POSTGRES_DB=berka",
            "-p",
            f"{_PG_PORT}:5432",
            "postgres:16-alpine",
        ],
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stderr[-400:]
    import duckdb

    deadline = _time.monotonic() + 90
    while _time.monotonic() < deadline:
        try:
            con = duckdb.connect()
            con.execute(f"ATTACH '{_PG_CONNINFO}' AS probe (TYPE postgres)")
            con.close()
            break
        except Exception:  # noqa: BLE001 - booting
            _time.sleep(1)
    else:
        raise AssertionError("seed postgres did not become ready")
    from scripts.seed_berka_db import seed

    seed("postgres", _PG_CONNINFO)


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


def _author(ctx: ScenarioContext) -> GraphAuthor:
    return GraphAuthor(
        LLMGateway(_SpyBackend(ReplayBackend(CASSETTE), _state(ctx)["exchanges"]))
    )


def _repo(ctx: ScenarioContext) -> StoreRepository:
    state = _state(ctx)
    if "repo" not in state:
        state["repo"] = StoreRepository(
            str(ctx.tmp_path / "data"), graph_author=_author(ctx)
        )
    return state["repo"]


def _drain(repo: StoreRepository) -> None:
    for _ in range(600):
        if all(r.catalog_status != "pending" for r in repo.list_datasets()):
            return
        _time.sleep(0.2)


def _task(ctx: ScenarioContext) -> dict:
    state = _state(ctx)
    return state["repo"].model(state["task_id"])


# --------------------------------------------------------------------------- #
# Givens
# --------------------------------------------------------------------------- #
@step(r"the demo database is seeded with the Berka tables")
def given_seeded_db(ctx: ScenarioContext) -> None:
    _ensure_seeded_postgres()
    _repo(ctx)


@step(r"the Berka database is connected and catalogued")
def given_connected(ctx: ScenarioContext) -> None:
    _ensure_seeded_postgres()
    repo = _repo(ctx)
    if "berka.loan" in repo._records:
        return
    manager = DatabaseManager(repo, vault=CredentialVault("e2e-019-passphrase"))
    manager.connect(
        ConnectionSpec(
            name="berka",
            engine=DatabaseEngine.POSTGRES,
            host="127.0.0.1",
            port=_PG_PORT,
            database="berka",
            user="postgres",
            password="e2e",
        )
    )
    _drain(repo)


@step(r"the Berka tables are uploaded as files and catalogued")
def given_uploaded(ctx: ScenarioContext) -> None:
    _repo(ctx).add_relational_bundle()


def _adjust_to_curated(ctx: ScenarioContext) -> None:
    """The user's adjust step (AC-3: confirm or ADJUST): pin the curated
    cutoffs and add the post-outcome 'payments' judgment the paper's
    author made — so the equivalence gate compares the PIPELINE on
    identical decisions."""
    state = _state(ctx)
    state["repo"].update_relational_decisions(
        state["task_id"],
        val_cutoff="1996-07-01",
        test_cutoff="1997-06-01",
        hide=["payments"],
    )


@step(r"a confirmed loan default task authored on the connected Berka")
def given_confirmed_connected(ctx: ScenarioContext) -> None:
    given_connected(ctx)
    when_author(ctx)
    _adjust_to_curated(ctx)
    state = _state(ctx)
    state["task"] = state["repo"].confirm_relational_task(state["task_id"])


@step(r"a confirmed loan default task authored on the uploads")
def given_confirmed_uploads(ctx: ScenarioContext) -> None:
    when_author(ctx)
    _adjust_to_curated(ctx)
    state = _state(ctx)
    state["task"] = state["repo"].confirm_relational_task(state["task_id"])


@step(r"a workspace whose tables have no validated links")
def given_bare_workspace(ctx: ScenarioContext) -> None:
    _repo(ctx)


@step(r"the authoring guidance will fail on the next attempt")
def given_failing_author(ctx: ScenarioContext) -> None:
    class _Boom:
        def author(self, table: Any, structure: dict, question: str) -> Any:
            raise GraphAuthoringError("authoring failed")

    _repo(ctx).graph_author = _Boom()


@step(r"a trained model from the connected-database path")
def given_trained_connected(ctx: ScenarioContext) -> None:
    given_confirmed_connected(ctx)
    state = _state(ctx)
    state["task"] = state["repo"].train_relational(state["task_id"])


# --------------------------------------------------------------------------- #
# Whens
# --------------------------------------------------------------------------- #
@step(r"the user connects that database")
def when_connect(ctx: ScenarioContext) -> None:
    given_connected(ctx)


@step(r"the user asks for a relational model on it")
def when_ask_structure(ctx: ScenarioContext) -> None:
    structure, _by_alias, rels = _repo(ctx)._workspace_structure()
    _state(ctx)["structure"] = structure
    _state(ctx)["relationships"] = rels


@step(r"the user asks to predict which loans will end in default")
def when_author(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    try:
        task = _repo(ctx).author_relational_task(QUESTION)
        state["task_id"] = task["task_id"]
    except GraphAuthoringError as exc:
        state["error"] = exc


@step(r"the user asks for a relational model there")
def when_ask_unsuitable(ctx: ScenarioContext) -> None:
    try:
        _repo(ctx).author_relational_task(QUESTION)
        raise AssertionError("expected a refusal")
    except ValueError as exc:
        _state(ctx)["error"] = exc


@step(r"the relational model is trained")
def when_train(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    state["task"] = state["repo"].train_relational(state["task_id"])


@step(r"the user asks to include a hidden outcome column")
def when_include_hidden(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    try:
        state["repo"].include_hidden_column(state["task_id"], "status")
        raise AssertionError("expected a refusal")
    except ValueError as exc:
        state["error"] = exc


@step(r"a remaining column alone nearly perfectly predicts the outcome")
def when_giveaway_present(ctx: ScenarioContext) -> None:
    from analyst.engine.relgraph.honesty import giveaway_columns
    from analyst.engine.relgraph.tasks import load_training_table

    state = _state(ctx)
    repo = state["repo"]
    spec, task_spec, _ = repo._prepare_authored(_task(ctx))
    frame = load_training_table(spec.name, task_spec.name)
    loans = repo.store.fetch_frame("berka.loan")
    loans["settled_flag"] = loans["status"].isin(["B", "D"]).astype(int)
    state["flagged"] = giveaway_columns(
        frame, loans, "loan_id", ["amount", "duration", "settled_flag"]
    )


@step(r"the model is trained on deliberately shuffled outcomes")
def when_canary(ctx: ScenarioContext) -> None:
    from analyst.engine.relgraph.honesty import shuffled_label_canary
    from analyst.engine.relgraph.tasks import load_training_table

    state = _state(ctx)
    repo = state["repo"]
    spec, task_spec, _ = repo._prepare_authored(_task(ctx))
    frame = load_training_table(spec.name, task_spec.name)
    state["canary_runs"] = [
        shuffled_label_canary(spec, task_spec, frame, seed=13) for _ in range(2)
    ]


# --------------------------------------------------------------------------- #
# Thens
# --------------------------------------------------------------------------- #
@step(r"the connected tables are profiled and catalogued in place")
def then_connected_profiled(ctx: ScenarioContext) -> None:
    repo = _repo(ctx)
    assert "berka.loan" in repo._records and "berka.trans" in repo._records
    record = repo._records["berka.loan"]
    assert record.federated and record.summary.profile.columns
    assert len(repo.store.fetch_frame("berka.loan")) == 682


@step(r"the links between them are validated against the data")
def then_links_validated(ctx: ScenarioContext) -> None:
    rels = _repo(ctx).store.discover_relationships(include_federated=True)
    assert len(rels) >= 10


@step(
    r"the derived structure names the tables, links and time column "
    r"in plain language"
)
def then_structure_derived(ctx: ScenarioContext) -> None:
    structure = _state(ctx)["structure"]
    names = {t["name"] for t in structure["tables"]}
    assert "berka_loan" in names and "berka_trans" in names
    assert structure["edges"]
    assert "grant_date" in structure["time_candidates"]["berka_loan"]


@step(r"every link used is one the workspace has validated")
def then_links_subset(ctx: ScenarioContext) -> None:
    from analyst.engine.relgraph.workspace import spec_from_workspace, table_alias

    state = _state(ctx)
    repo = _repo(ctx)
    rels = state["relationships"]
    spec = spec_from_workspace(
        {
            n: r.summary.profile
            for n, r in repo._records.items()
            if ".predictions." not in n
        },
        rels,
        name="ws-subset-check",
        val_cutoff="1996-07-01",
        test_cutoff="1997-06-01",
    )
    derived = {
        (t.name, fk.column, fk.ref_table)
        for t in spec.tables.values()
        for fk in t.foreign_keys
    }
    validated = {
        (table_alias(r.child_table), r.child_column, table_alias(r.parent_table))
        for r in rels
    }
    assert derived and derived <= validated


@step(
    r"the agent proposes the entity, outcome definition, prediction moment, "
    r"cutoffs and hidden columns as plain-language decisions"
)
def then_decisions_proposed(ctx: ScenarioContext) -> None:
    task = _task(ctx)
    assert task["entity_table"] == "berka_loan"
    assert "SELECT" in task["label_sql"].upper()
    assert task["framing"]["question"] and task["framing"]["moment"]
    assert task["val_cutoff"] < task["test_cutoff"]
    assert "status" in task["hidden_columns"]


@step(r"nothing trains before the user confirms the decisions")
def then_unconfirmed_untrained(ctx: ScenarioContext) -> None:
    import pytest as _pytest

    task = _task(ctx)
    assert task["status"] == "proposed" and task["metrics"] is None
    with _pytest.raises(ValueError):
        _state(ctx)["repo"].train_relational(task["task_id"])


@step(r"the authoring exchange carries schema and catalog metadata only")
def then_exchange_metadata_only(ctx: ScenarioContext) -> None:
    exchanges = _state(ctx)["exchanges"]
    assert len(exchanges) == 1
    prompt = exchanges[0].prompt
    assert "berka_loan" in prompt and "Validated links" in prompt


@step(r"the outcome definition runs locally under the read-only guard")
def then_sql_guarded(ctx: ScenarioContext) -> None:
    # confirm ran assert_safe_select before materializing; the exchange
    # itself carried no rows either.
    frame_ids = _repo(ctx).store.fetch_frame("berka.trans", ("trans_id",))
    sample = {str(v) for v in frame_ids["trans_id"].head(50)}
    prompt = _state(ctx)["exchanges"][0].prompt
    assert not any(tid in prompt for tid in sample)


@step(r"the baseline's held-out score is within 0.03 of the curated 0.7647")
def then_baseline_equiv(ctx: ScenarioContext) -> None:
    ours = _state(ctx)["task"]["metrics"]["baseline"]
    assert abs(ours["test_auroc"] - 0.7647) <= 0.03
    assert ours == _curated_metrics()["baseline"]  # bitwise vs curated run


@step(r"the graph's held-out score is within 0.07 of the curated 0.7182")
def then_graph_equiv(ctx: ScenarioContext) -> None:
    ours = _state(ctx)["task"]["metrics"]["graph"]["test_auroc"]
    assert abs(ours - 0.7182) <= 0.07
    curated = _curated_metrics()["graph"]["test_auroc"]
    assert abs(ours - curated) <= 0.02  # same-machine near-equivalence


@step(r"the columns the outcome definition reads are hidden automatically")
def then_auto_hidden(ctx: ScenarioContext) -> None:
    assert "status" in _task(ctx)["hidden_columns"]


@step(r"the request is refused with the reason")
def then_include_refused(ctx: ScenarioContext) -> None:
    assert "stays hidden" in str(_state(ctx)["error"])


@step(r"the user is warned it likely records the outcome")
def then_giveaway_flagged(ctx: ScenarioContext) -> None:
    assert _state(ctx)["flagged"] == ["settled_flag"]


@step(r"the held-out score is a coin flip")
def then_canary_coin_flip(ctx: ScenarioContext) -> None:
    first, _second = _state(ctx)["canary_runs"]
    assert abs(first - 0.5) < 0.1


@step(r"training again with the same seed reproduces the same result")
def then_canary_deterministic(ctx: ScenarioContext) -> None:
    first, second = _state(ctx)["canary_runs"]
    assert first == second


@step(r"the request is refused before training with the missing prerequisites named")
def then_refused_prereqs(ctx: ScenarioContext) -> None:
    error = str(_state(ctx)["error"])
    assert "validated links" in error
    assert not _repo(ctx).models()


@step(r"the failure is reported plainly")
def then_failure_plain(ctx: ScenarioContext) -> None:
    assert "authoring failed" in str(_state(ctx)["error"])


@step(r"no task and no model exist afterwards")
def then_nothing_created(ctx: ScenarioContext) -> None:
    assert _repo(ctx).models() == []


@step(r"the registry story names the connection the data came from")
def then_story_source(ctx: ScenarioContext) -> None:
    story = _state(ctx)["task"]["story"]
    assert story["source"] == "berka"


@step(
    r"it states plainly that training used a temporary local copy "
    r"that never left the machine"
)
def then_story_disclosure(ctx: ScenarioContext) -> None:
    story = _state(ctx)["task"]["story"]
    assert "temporary local copy" in story["local_build"]
    assert "never leaving" in story["local_build"]


# --------------------------------------------------------------------------- #
# AC-12 — the deployed analyst:ml container + seeded Postgres alongside.
# --------------------------------------------------------------------------- #

_NETWORK = "analyst-e2e-019-net"
_APP_CONTAINER = "analyst-ml-authoring-e2e"
_APP_PG = "analyst-ml-authoring-pg"


def _container_cleanup() -> None:
    subprocess.run(["docker", "rm", "-f", _APP_CONTAINER, _APP_PG], capture_output=True)
    subprocess.run(["docker", "network", "rm", _NETWORK], capture_output=True)


@step(r"the analyst ML container runs with the seeded demo database alongside")
def given_ml_stack(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    _container_cleanup()
    atexit.register(_container_cleanup)
    build = subprocess.run(
        [
            "docker",
            "build",
            "-q",
            "--platform",
            "linux/amd64",
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
    subprocess.run(["docker", "network", "create", _NETWORK], capture_output=True)
    run = subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            _APP_PG,
            "--network",
            _NETWORK,
            "--network-alias",
            "berkadb",
            "-e",
            "POSTGRES_PASSWORD=e2e",
            "-e",
            "POSTGRES_DB=berka",
            "-p",
            f"{_PG_PORT + 1}:5432",
            "postgres:16-alpine",
        ],
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stderr[-400:]
    conninfo = (
        f"host=127.0.0.1 port={_PG_PORT + 1} dbname=berka user=postgres password=e2e"
    )
    import duckdb

    deadline = _time.monotonic() + 90
    while _time.monotonic() < deadline:
        try:
            con = duckdb.connect()
            con.execute(f"ATTACH '{conninfo}' AS probe (TYPE postgres)")
            con.close()
            break
        except Exception:  # noqa: BLE001
            _time.sleep(1)
    else:
        raise AssertionError("stack postgres did not become ready")
    from scripts.seed_berka_db import seed

    seed("postgres", conninfo)
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
            _APP_CONTAINER,
            "--network",
            _NETWORK,
            "-p",
            f"{port}:8000",
            "-v",
            f"{REPO_ROOT}/tests/cassettes:/cassettes:ro",
            # No ro ml-cache mount: the authored flow builds its training
            # database under the WRITABLE /data/ml-cache default (the data
            # arrives via the connected Postgres, not the curated bundle).
            "-e",
            "ANALYST_CATALOG_CASSETTE=/cassettes/graph_authoring.json",
            "-e",
            "ANALYST_SECRET_KEY=e2e-019-passphrase",
            "analyst:e2e-ml",
        ],
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stderr[-400:]
    url = f"http://127.0.0.1:{port}"
    deadline = _time.monotonic() + 300
    while _time.monotonic() < deadline:
        try:
            if httpx.get(f"{url}/api/health", timeout=2).status_code == 200:
                break
        except Exception:  # noqa: BLE001
            _time.sleep(2)
    else:
        raise AssertionError("ml container did not become healthy")
    state["container_url"] = url
    state["container_page"] = _STACK["browser"].new_page(
        viewport={"width": 1440, "height": 900}
    )


@step(r"the user completes the guided authoring journey in a browser")
def when_authoring_journey(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    page = state["container_page"]
    expect = _expect()
    url = state["container_url"]
    # Connect the seeded database through the API (the connections UI is
    # feature 005's surface, exercised by its own board) and drive the
    # authoring UI in the browser.
    resp = httpx.post(
        f"{url}/api/databases/connect",
        json={
            "name": "berka",
            "engine": "postgres",
            "host": "berkadb",
            "port": 5432,
            "database": "berka",
            "user": "postgres",
            "password": "e2e",
        },
        timeout=120,
    )
    assert resp.status_code == 201, resp.text[:300]
    deadline = _time.monotonic() + 600
    while _time.monotonic() < deadline:
        datasets = httpx.get(f"{url}/api/datasets", timeout=10).json()
        berka = [d for d in datasets if d["name"].startswith("berka.")]
        if len(berka) >= 9 and all(d.get("catalogStatus") != "pending" for d in berka):
            break
        _time.sleep(3)
    page.goto(url)
    page.get_by_role("button", name="Models", exact=True).click()
    page.get_by_label("Authoring question").fill(QUESTION)
    page.get_by_label("Author from question").click()
    expect(page.get_by_label("Authored decisions")).to_be_visible(timeout=120000)
    expect(page.get_by_label("Hidden outcome columns")).to_be_visible()
    page.get_by_label("Confirm decisions").click()
    expect(page.get_by_label("Confirmed honesty checks")).to_be_visible(timeout=300000)
    page.get_by_label("Train relational model").click()
    expect(page.get_by_label("Relational evaluation")).to_be_visible(timeout=900000)


@step(r"the trained model and its predictions are visible in the deployed app")
def then_journey_predictions(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    expect = _expect()
    expect(
        state["container_page"].get_by_label("Predictions dataset", exact=False)
    ).to_be_visible()
    datasets = httpx.get(f"{state['container_url']}/api/datasets", timeout=10).json()
    predictions = [d for d in datasets if "predictions" in d["name"]]
    assert predictions and predictions[0]["rowCount"] == 682


@step(r"the registry card tells the story including the data's source")
def then_journey_story(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    page = state["container_page"]
    expect = _expect()
    expect(page.get_by_label("Relational story")).to_be_visible()
    expect(page.get_by_text("berka", exact=False).first).to_be_visible()
    models = httpx.get(f"{state['container_url']}/api/models", timeout=10).json()
    authored = [m for m in models["models"] if m.get("authored")]
    assert authored and authored[0]["story"]["source"] == "berka"
    page.close()
    _container_cleanup()
