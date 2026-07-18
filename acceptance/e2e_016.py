"""Step handlers for feature 016 — catalog curation.

Curation scenarios bind over the in-process seam (StoreRepository in the
scenario tmp_path); agent synthesis replays the curation cassette so the
board is deterministic and offline. Workbench flows bind to Playwright
against the fixtures app. Bindings land per slice; unbound steps fail
NOT YET IMPLEMENTED — the intended red.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

from acceptance.e2e_base import (
    _STACK,
    ScenarioContext,
    _e2e_fresh,
    _e2e_stack,
    expect_,
    make_registry,
)
from analyst.agentic.curation import CurationError, Curator
from analyst.agentic.gateway import LLMGateway, LLMRequest, ReplayBackend
from analyst.api.qa import PlannerQAService
from analyst.api.repository import StoreRepository
from analyst.domain.catalog import Clarification, UnknownCurationError

step, run_step = make_registry()
_expect = expect_

__all__ = ["ScenarioContext", "run_step", "_e2e_stack", "_e2e_fresh"]


REPO_ROOT = Path(__file__).resolve().parent.parent
CURATION_CASSETTE = str(REPO_ROOT / "tests" / "cassettes" / "curation.json")
CURATION_PLANNER_CASSETTE = str(
    REPO_ROOT / "tests" / "cassettes" / "curation_planner.json"
)

ORDERS = (
    "order_id,status,amount\n"
    "O1,fulfilled,10\nO2,unfulfilled,20\nO3,fulfilled,30\n"
    "O4,unfulfilled,40\nO5,fulfilled,50\nO6,fulfilled,60\n"
)
DATED = (
    "order_id,order_date,amount\nO1,2026-01-05,10\nO2,2026-02-06,20\nO3,2026-03-07,30\n"
)
CLARIFICATION = Clarification(
    question="What does the 'status' column describe?",
    options=(
        "Account/subscription state of the customer",
        "Fulfillment state of a sale or order",
        "Payment state (paid/pending/failed)",
    ),
    column="status",
)


class _SpyBackend:
    """Wraps the replay backend, capturing every prompt for AC-11."""

    def __init__(self, inner: ReplayBackend, log: list):
        self.inner, self.log = inner, log

    def complete(self, request: LLMRequest) -> str:
        self.log.append(request)
        return self.inner.complete(request)


def _state(ctx: ScenarioContext) -> dict[str, Any]:
    if not isinstance(ctx.data, dict):
        ctx.data = {"exchanges": []}
    return ctx.data


def _repo(ctx: ScenarioContext) -> StoreRepository:
    state = _state(ctx)
    if "repo" not in state:
        if state.get("offline"):
            curator = None
        elif state.get("failing"):

            class _Boom:
                def complete(self, *a: Any, **k: Any) -> Any:
                    raise CurationError("synthesis failed")

            curator = _Boom()
        else:
            curator = Curator(
                LLMGateway(
                    _SpyBackend(ReplayBackend(CURATION_CASSETTE), state["exchanges"])
                )
            )
        state["repo"] = StoreRepository(str(ctx.tmp_path / "data"), curator=curator)
    return state["repo"]


def _seed_orders(ctx: ScenarioContext, text: str, clarify: bool) -> str:
    repo = _repo(ctx)
    (rec,) = repo.ingest("orders.csv", text.encode())
    entry = rec.summary.catalog
    if clarify:
        entry = dataclasses.replace(entry, clarifications=(CLARIFICATION,))
    repo.attach_catalog(rec.name, entry)
    state = _state(ctx)
    state["dataset"] = rec.name
    state["before"] = repo.get_dataset(rec.name).summary.catalog
    return rec.name


def _entry(ctx: ScenarioContext):  # noqa: ANN202
    state = _state(ctx)
    return state["repo"].get_dataset(state["dataset"]).summary.catalog


def _column(ctx: ScenarioContext, name: str):  # noqa: ANN202
    return next(c for c in _entry(ctx).columns if c.name == name)


# --------------------------------------------------------------------------- #
# Givens
# --------------------------------------------------------------------------- #
@step(r'an ingested orders file whose catalog asks what the "status" column describes')
def given_orders_with_clarification(ctx: ScenarioContext) -> None:
    _seed_orders(ctx, ORDERS, clarify=True)


@step(r'an ingested orders file with a catalogued "order_date" column')
def given_orders_with_date(ctx: ScenarioContext) -> None:
    _seed_orders(ctx, DATED, clarify=False)


@step(r"a second ingested customers file with its own catalog")
def given_customers_file(ctx: ScenarioContext) -> None:
    repo = _repo(ctx)
    (rec,) = repo.ingest("customers.csv", b"customer_id,region\nC1,East\nC2,West\n")
    state = _state(ctx)
    state["other"] = rec.name
    state["other_before"] = repo.get_dataset(rec.name).summary.catalog


@step(r"the app runs offline with no AI features available")
def given_offline(ctx: ScenarioContext) -> None:
    _state(ctx)["offline"] = True


@step(r"the semantic analysis will fail on the next attempt")
def given_failing(ctx: ScenarioContext) -> None:
    # rebuild the repo over the same data dir with a failing curator
    state = _state(ctx)
    state["failing"] = True
    state.pop("repo", None)
    _repo(ctx)
    state["before"] = _entry(ctx)


@step(r'the clarification is answered with "(?P<answer>[^"]+)"')
def given_clarification_answered(ctx: ScenarioContext, answer: str) -> None:
    state = _state(ctx)
    state["repo"].answer_clarification(state["dataset"], "status", answer)


# --------------------------------------------------------------------------- #
# Whens
# --------------------------------------------------------------------------- #
@step(r"the user reviews the open clarifications")
def when_review_clarifications(ctx: ScenarioContext) -> None:
    _state(ctx)["clarifications"] = _entry(ctx).clarifications


@step(r'the user answers the clarification with "(?P<answer>[^"]+)"')
def when_answer(ctx: ScenarioContext, answer: str) -> None:
    state = _state(ctx)
    try:
        state["repo"].answer_clarification(state["dataset"], "status", answer)
        state["error"] = None
    except CurationError as exc:
        state["error"] = exc


@step(r'the user answers the clarification in their own words: "(?P<answer>[^"]+)"')
def when_answer_freeform(ctx: ScenarioContext, answer: str) -> None:
    when_answer(ctx, answer)


@step(r'the user suggests the correction "(?P<note>[^"]+)"')
def when_correct_column(ctx: ScenarioContext, note: str) -> None:
    state = _state(ctx)
    if "repo" in state:  # in-process seam
        column = (
            "order_date"
            if any(c.name == "order_date" for c in _entry(ctx).columns)
            else "status"
        )
        state["repo"].suggest_correction(state["dataset"], column, note)
        state["corrected_column"] = column
        return
    # browser flow (fixtures app)
    expect = _expect()
    ctx.page.get_by_label("Suggest a correction for billing_region").click()
    ctx.page.get_by_label("Correction", exact=True).fill(note)
    ctx.page.get_by_role("button", name="Submit correction").click()
    expect(
        ctx.page.get_by_label("Human-confirmed meaning for billing_region").first
    ).to_be_visible()


@step(r'the user suggests the table correction "(?P<note>[^"]+)"')
def when_correct_table(ctx: ScenarioContext, note: str) -> None:
    state = _state(ctx)
    state["repo"].suggest_correction(state["dataset"], None, note)


@step(r"the dataset is re-catalogued automatically")
def when_recatalogued(ctx: ScenarioContext) -> None:
    from analyst.domain.catalog import CatalogEntry, ColumnDescription

    state = _state(ctx)
    fresh = CatalogEntry(
        table_description="Rederived table text.",
        columns=tuple(
            ColumnDescription(c.name, "Rederived description.", c.role)
            for c in _entry(ctx).columns
        ),
        clarifications=(CLARIFICATION,),
    )
    state["repo"].attach_catalog(state["dataset"], fresh)


@step(r"the app restarts")
def when_app_restarts(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    state["repo"] = StoreRepository(str(ctx.tmp_path / "data"))


@step(r"the user asks which orders are not yet fulfilled")
def when_ask_unfulfilled(ctx: ScenarioContext) -> None:
    from analyst.agentic.planner import QueryPlanner

    state = _state(ctx)
    service = PlannerQAService(
        QueryPlanner(LLMGateway(ReplayBackend(CURATION_PLANNER_CASSETTE)))
    )
    state["qa_answer"] = service.submit(
        "Which orders are not yet fulfilled?", state["repo"]
    )


@step(r"the user submits an empty answer")
def when_empty_answer(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    try:
        state["repo"].answer_clarification(state["dataset"], "status", "   ")
        state["error"] = None
    except ValueError as exc:
        state["error"] = exc


@step(r"the user answers a clarification that does not exist")
def when_answer_missing(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    try:
        state["repo"].answer_clarification(state["dataset"], "ghost", "whatever")
        state["error"] = None
    except UnknownCurationError as exc:
        state["error"] = exc


# --------------------------------------------------------------------------- #
# Thens
# --------------------------------------------------------------------------- #
@step(r"the clarification offers its options and accepts a custom answer")
def then_clarification_shape(ctx: ScenarioContext) -> None:
    (clar,) = _state(ctx)["clarifications"]
    assert len(clar.options) >= 2 and clar.column == "status"
    # free-form acceptance is proven by the free-form scenario; here we pin
    # that the options carry the offered meanings verbatim
    assert "Fulfillment state of a sale or order" in clar.options


@step(r'the "status" column\'s description states the fulfillment meaning')
def then_status_fulfillment(ctx: ScenarioContext) -> None:
    assert "fulfillment" in _column(ctx, "status").description.lower()


@step(r"no clarification remains open for the dataset")
def then_no_clarifications(ctx: ScenarioContext) -> None:
    assert _entry(ctx).clarifications == ()


@step(r'the "status" column\'s description reflects the returns-process meaning')
def then_status_returns(ctx: ScenarioContext) -> None:
    assert "return" in _column(ctx, "status").description.lower()


@step(r"the customers catalog is entirely unchanged")
def then_customers_unchanged(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    now = state["repo"].get_dataset(state["other"]).summary.catalog
    assert now == state["other_before"]


@step(r'only the "status" column and the orders table description may differ')
def then_blast_radius(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    before = {c.name: c for c in state["before"].columns}
    for column in _entry(ctx).columns:
        if column.name != "status":
            assert column.description == before[column.name].description


@step(r'the "status" column is (?:still )?marked human-confirmed')
def then_status_confirmed(ctx: ScenarioContext) -> None:
    state = _state(ctx)["repo"].curation(_state(ctx)["dataset"])
    assert state["columns"]["status"]["kind"] == "answer"


@step(r"the recorded provenance carries the given answer")
def then_provenance(ctx: ScenarioContext) -> None:
    state = _state(ctx)["repo"].curation(_state(ctx)["dataset"])
    assert state["columns"]["status"]["input"] == "Fulfillment state of a sale or order"


@step(r'the "status" column\'s description still states the fulfillment meaning')
def then_still_fulfillment(ctx: ScenarioContext) -> None:
    then_status_fulfillment(ctx)


@step(r'the "order_date" column\'s description reflects the settlement meaning')
def then_order_date_settlement(ctx: ScenarioContext) -> None:
    assert "settlement" in _column(ctx, "order_date").description.lower()


@step(r"the column is (?:still )?marked human-confirmed")
def then_column_confirmed(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    curation = state["repo"].curation(state["dataset"])
    column = state.get("corrected_column", "status")
    assert column in curation["columns"]


@step(r"the orders table description reflects the wholesale meaning")
def then_table_wholesale(ctx: ScenarioContext) -> None:
    assert "wholesale" in _entry(ctx).table_description.lower()


@step(r"the table is marked human-confirmed")
def then_table_confirmed(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    assert state["repo"].curation(state["dataset"])["table"] is not None


@step(r'the "status" column\'s description plainly records the chosen meaning')
def then_status_templated(ctx: ScenarioContext) -> None:
    description = _column(ctx, "status").description
    assert "Fulfillment state of a sale or order" in description


@step(r"the column is marked human-confirmed and awaiting reconciliation")
def then_confirmed_pending(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    curation = state["repo"].curation(state["dataset"])
    column = state.get("corrected_column", "status")
    assert curation["columns"][column]["pending_reconciliation"] is True


@step(r'the "order_date" column\'s description is exactly the suggested words')
def then_order_date_verbatim(ctx: ScenarioContext) -> None:
    assert (
        _column(ctx, "order_date").description
        == "This is the settlement date, not the order date"
    )


@step(r"the answer counts only the orders whose status is unfulfilled")
def then_answer_unfulfilled(ctx: ScenarioContext) -> None:
    answer = _state(ctx)["qa_answer"]
    assert answer.abstain is False
    text = str(answer.stat.value if answer.stat else answer.summary)
    assert "2" in text, text


@step(
    r"the exchange sent for completion carries profile facts, catalog text and the answer"
)
def then_exchange_contents(ctx: ScenarioContext) -> None:
    (request,) = _state(ctx)["exchanges"]
    prompt = request.prompt
    assert "Fulfillment state of a sale or order" in prompt
    assert "distinct=" in prompt and "Current table description" in prompt


@step(r"the exchange carries no data rows")
def then_exchange_no_rows(ctx: ScenarioContext) -> None:
    (request,) = _state(ctx)["exchanges"]
    assert "O1" not in request.prompt and "O6" not in request.prompt


@step(r"the submission is rejected with a message")
def then_rejected_message(ctx: ScenarioContext) -> None:
    assert isinstance(_state(ctx)["error"], ValueError)


@step(r"the action is rejected as not found")
def then_not_found(ctx: ScenarioContext) -> None:
    assert isinstance(_state(ctx)["error"], UnknownCurationError)


@step(r"the catalog is unchanged")
def then_catalog_unchanged(ctx: ScenarioContext) -> None:
    assert _entry(ctx) == _state(ctx)["before"]


@step(r"the failure is reported plainly")
def then_failure_reported(ctx: ScenarioContext) -> None:
    assert isinstance(_state(ctx)["error"], CurationError)


@step(r"the catalog is unchanged and the clarification remains open")
def then_unchanged_still_open(ctx: ScenarioContext) -> None:
    assert _entry(ctx) == _state(ctx)["before"]
    assert len(_entry(ctx).clarifications) == 1


# --------------------------------------------------------------------------- #
# Workbench flows (browser) — fixtures app
# --------------------------------------------------------------------------- #
@step(r"the analyst app is open in a browser")
def given_app_open(ctx: ScenarioContext) -> None:
    expect = _expect()
    ctx.page.goto(_STACK["web"])
    expect(ctx.page.get_by_text("Catalog", exact=True).first).to_be_visible()
    ctx.page.evaluate("window.__no_reload_pin = 1")


@step(r"the user opens the sample sales table in the workbench")
def when_open_sales(ctx: ScenarioContext) -> None:
    ctx.page.get_by_role("button", name="Open table sales").first.click()


@step(r"the user answers its open clarification with the sales-channel option")
def when_answer_in_workbench(ctx: ScenarioContext) -> None:
    expect = _expect()
    card = ctx.page.get_by_label("Clarification about channel")
    expect(card).to_be_visible()
    card.get_by_text("Sales channel the order was placed through", exact=True).click()
    card.get_by_role("button", name="Submit answer").click()


@step(r"the clarification disappears without a page reload")
def then_clarification_gone(ctx: ScenarioContext) -> None:
    expect = _expect()
    expect(ctx.page.get_by_label("Clarification about channel")).to_have_count(0)
    assert ctx.page.evaluate("window.__no_reload_pin") == 1, "the page reloaded"


@step(r"the settled column shows a human-confirmed badge")
def then_settled_badge(ctx: ScenarioContext) -> None:
    expect = _expect()
    expect(
        ctx.page.get_by_label("Human-confirmed meaning for channel").first
    ).to_be_visible()


@step(r'the user opens the column "(?P<column>[^"]+)" of the sample sales table')
def when_open_column_of_sales(ctx: ScenarioContext, column: str) -> None:
    ctx.page.get_by_role("button", name="Open table sales").first.click()
    ctx.page.get_by_role("button", name=f"Column {column}").click()


@step(r"the column shows a human-confirmed badge without a page reload")
def then_column_badge_no_reload(ctx: ScenarioContext) -> None:
    expect = _expect()
    expect(
        ctx.page.get_by_label("Human-confirmed meaning for billing_region").first
    ).to_be_visible()
    assert ctx.page.evaluate("window.__no_reload_pin") == 1, "the page reloaded"
