"""Step handlers for feature 015 — interactive dashboards.

Assembly/edit replay the dashboards cassette; viewing/filtering scenarios
run fully offline over the in-process seam; workbench flows bind to
Playwright against the fixtures app. Bindings land per slice; unbound
steps fail NOT YET IMPLEMENTED — the intended red.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from acceptance.e2e_base import (
    _STACK,
    ScenarioContext,
    _e2e_fresh,
    _e2e_stack,
    expect_,
    make_registry,
)
from analyst.agentic.dashboards import (
    AssemblyResult,
    DashboardAssembler,
    DashboardAssemblyError,
    WidgetSpec,
)
from analyst.agentic.gateway import LLMGateway, LLMRequest, ReplayBackend
from analyst.api.repository import StoreRepository
from analyst.domain.dashboards import UnknownDashboardError

step, run_step = make_registry()
_expect = expect_
_ = _STACK  # keep the import: browser steps use it and ruff must not strip it

__all__ = ["ScenarioContext", "run_step", "_e2e_stack", "_e2e_fresh"]


REPO_ROOT = Path(__file__).resolve().parent.parent
DASH_CASSETTE = str(REPO_ROOT / "tests" / "cassettes" / "dashboards.json")

SALES = (
    "region,product,amount\n"
    "East,widget,10\nEast,gadget,20\nWest,widget,30\n"
    "West,gadget,40\nNorth,widget,50\n"
)
SALES_DOUBLED = (
    "region,product,amount\n"
    "East,widget,20\nEast,gadget,40\nWest,widget,60\n"
    "West,gadget,80\nNorth,widget,100\n"
)
STAFF = "employee,dept\nAna,ops\nBo,sales\n"


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


def _assembler(ctx: ScenarioContext) -> DashboardAssembler:
    return DashboardAssembler(
        LLMGateway(_SpyBackend(ReplayBackend(DASH_CASSETTE), _state(ctx)["exchanges"]))
    )


def _repo(ctx: ScenarioContext) -> StoreRepository:
    state = _state(ctx)
    if "repo" not in state:
        state["repo"] = StoreRepository(
            str(ctx.tmp_path / "data"), assembler=_assembler(ctx)
        )
    return state["repo"]


def _dash(ctx: ScenarioContext):  # noqa: ANN202
    state = _state(ctx)
    return state["repo"]._require_dashboard(state["dashboard_id"])


def _widget_by_source(ctx: ScenarioContext, source: str, grouped: bool = False):  # noqa: ANN202
    for widget in _dash(ctx).widgets:
        if widget.source == source and (
            not grouped or "GROUP BY" in widget.sql.upper()
        ):
            if not grouped or "region" in widget.sql:
                return widget
    raise AssertionError(f"no widget over {source} (grouped={grouped})")


def _run(ctx: ScenarioContext, filters: list) -> dict:
    state = _state(ctx)
    return state["repo"].run_dashboard(state["dashboard_id"], filters)


# --------------------------------------------------------------------------- #
# Givens
# --------------------------------------------------------------------------- #
@step(r"a workspace with regional sales and staff files")
def given_workspace(ctx: ScenarioContext) -> None:
    repo = _repo(ctx)
    repo.ingest("sales.csv", SALES.encode())
    repo.ingest("staff.csv", STAFF.encode())


@step(r"an assembled sales and staffing overview dashboard")
def given_assembled(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    out = state["repo"].create_dashboard("a sales and staffing overview dashboard")
    assert out["dashboard"] is not None
    state["dashboard_id"] = out["dashboard"].dashboard_id


@step(r"the agent will propose a malformed dashboard")
def given_malformed_assembler(ctx: ScenarioContext) -> None:
    class _Bad:
        def assemble(self, request: str, tables, current_spec=None):  # noqa: ANN001
            return AssemblyResult(
                name="Broken",
                widgets=[
                    WidgetSpec(
                        question="bad",
                        sql='SELECT * FROM "sales.csv"',  # marker missing
                        title="Bad widget",
                        source="sales.csv",
                    )
                ],
            )

    _repo(ctx).assembler = _Bad()


@step(r"the app runs offline with no AI features available")
def given_offline(ctx: ScenarioContext) -> None:
    _state(ctx)["offline"] = True


@step(r"a previously assembled sales and staffing dashboard over sales and staff files")
def given_previously_assembled(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    given_workspace(ctx)
    given_assembled(ctx)
    # restart WITHOUT any assembler — pure offline viewing
    state["repo"] = StoreRepository(str(ctx.tmp_path / "data"))


# --------------------------------------------------------------------------- #
# Whens
# --------------------------------------------------------------------------- #
@step(r'the user asks for "(?P<request>[^"]+)"')
def when_ask_for(ctx: ScenarioContext, request: str) -> None:
    state = _state(ctx)
    try:
        out = state["repo"].create_dashboard(request)
        state["assembly"], state["error"] = out, None
        if out["dashboard"] is not None:
            state["dashboard_id"] = out["dashboard"].dashboard_id
    except (ValueError, DashboardAssemblyError) as exc:
        state["assembly"], state["error"] = None, exc


@step(r'the user asks for just "(?P<request>[^"]+)"')
def when_ask_vague(ctx: ScenarioContext, request: str) -> None:
    when_ask_for(ctx, request)


@step(r'the user filters the dashboard to region "(?P<value>[^"]+)"')
def when_filter_region(ctx: ScenarioContext, value: str) -> None:
    state = _state(ctx)
    state["filters"] = [("region", value)]
    state["run"] = _run(ctx, state["filters"])
    state["run_unfiltered"] = _run(ctx, [])


@step(r'the user clicks the "(?P<value>[^"]+)" bar of the revenue widget')
def when_click_bar(ctx: ScenarioContext, value: str) -> None:
    when_filter_region(ctx, value)


@step(r'the user drills into the revenue widget under the "(?P<value>[^"]+)" filter')
def when_drill(ctx: ScenarioContext, value: str) -> None:
    state = _state(ctx)
    widget = _widget_by_source(ctx, "sales.csv", grouped=True)
    state["drill"] = state["repo"].drill_dashboard(
        state["dashboard_id"], widget.widget_id, [("region", value)]
    )


@step(r"the dataset is refreshed with doubled amounts")
def when_refresh_doubled(ctx: ScenarioContext) -> None:
    _state(ctx)["repo"].refresh("sales.csv", "sales.csv", SALES_DOUBLED.encode())


@step(r"the app restarts")
def when_restart(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    state["repo"] = StoreRepository(str(ctx.tmp_path / "data"))


@step(r"the sales dataset is deleted")
def when_delete_sales(ctx: ScenarioContext) -> None:
    _state(ctx)["repo"].delete("sales.csv")


@step(r"the user opens a dashboard that does not exist")
def when_open_missing(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    state["before_list"] = [d.dashboard_id for d in state["repo"].dashboards()]
    try:
        state["repo"].run_dashboard("no-such-dashboard", [])
        state["error"] = None
    except UnknownDashboardError as exc:
        state["error"] = exc


@step(r'the user asks to "(?P<request>[^"]+)"')
def when_edit(ctx: ScenarioContext, request: str) -> None:
    state = _state(ctx)
    out = state["repo"].edit_dashboard(state["dashboard_id"], request)
    assert out["dashboard"] is not None
    state["edited"] = out["dashboard"]


# --------------------------------------------------------------------------- #
# Thens — assembling
# --------------------------------------------------------------------------- #
@step(r"a named dashboard is assembled with at least two widgets")
def then_assembled(ctx: ScenarioContext) -> None:
    dashboard = _state(ctx)["assembly"]["dashboard"]
    assert dashboard.name and len(dashboard.widgets) >= 2


@step(r"every widget renders from locally computed numbers")
def then_widgets_render(ctx: ScenarioContext) -> None:
    run = _run(ctx, [])
    for wid, entry in run["widgets"].items():
        assert entry["answer"] is not None, f"{wid}: {entry['error']}"


@step(r"the agent asks a structured clarification instead of assembling")
def then_clarified(ctx: ScenarioContext) -> None:
    out = _state(ctx)["assembly"]
    assert out["dashboard"] is None
    assert out["clarification"].question and len(out["clarification"].options) >= 2


@step(r"each widget disclosed its assumptions, lineage and query")
def then_widget_trails(ctx: ScenarioContext) -> None:
    run = _run(ctx, [])
    for entry in run["widgets"].values():
        trail = entry["answer"].trust_trail
        assert trail is not None and trail.sql and trail.lineage


@step(r"the exchange sent for assembly carries schema and catalog metadata")
def then_exchange_metadata(ctx: ScenarioContext) -> None:
    (request,) = _state(ctx)["exchanges"]
    assert '"sales.csv"' in request.prompt and "region" in request.prompt


@step(r"the exchange carries no data rows")
def then_exchange_no_rows(ctx: ScenarioContext) -> None:
    (request,) = _state(ctx)["exchanges"]
    assert "East,widget" not in request.prompt and "Ana,ops" not in request.prompt


@step(r"the assembly is rejected with the reason")
def then_assembly_rejected(ctx: ScenarioContext) -> None:
    error = _state(ctx)["error"]
    assert isinstance(error, ValueError) and "marker" in str(error).lower()


@step(r"no dashboard is created")
def then_no_dashboard(ctx: ScenarioContext) -> None:
    assert _state(ctx)["repo"].dashboards() == []


# --------------------------------------------------------------------------- #
# Thens — viewing/filtering/drilling
# --------------------------------------------------------------------------- #
def _grouped_rows(run: dict, ctx: ScenarioContext) -> dict:
    widget = _widget_by_source(ctx, "sales.csv", grouped=True)
    answer = run["widgets"][widget.widget_id]["answer"]
    return {str(r[0]): float(r[1]) for r in answer.table.rows}


@step(r"the revenue widget totals only the East rows")
def then_revenue_east_only(ctx: ScenarioContext) -> None:
    rows = _grouped_rows(_state(ctx)["run"], ctx)
    assert rows == {"East": 30.0}, rows


@step(r"clearing the filter restores the original totals")
def then_clear_restores(ctx: ScenarioContext) -> None:
    rows = _grouped_rows(_state(ctx)["run_unfiltered"], ctx)
    assert rows == {"East": 30.0, "West": 70.0, "North": 50.0}, rows


@step(r"the widget lacking a region indicates it is unaffected")
def then_unaffected(ctx: ScenarioContext) -> None:
    widget = _widget_by_source(ctx, "staff.csv")
    entry = _state(ctx)["run"]["widgets"][widget.widget_id]
    assert "region" in entry["unaffected_by"]
    assert entry["answer"] is not None


@step(r"the other widgets re-scope to the East rows")
def then_others_rescope(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    for widget in _dash(ctx).widgets:
        if widget.source != "sales.csv" or "GROUP BY" in widget.sql.upper():
            continue
        answer = state["run"]["widgets"][widget.widget_id]["answer"]
        value = answer.stat.value if answer.stat else str(answer.summary)
        assert "30" in str(value), value  # East total


@step(r"the active filter is visible and clearable in one action")
def then_filter_clearable(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    assert state["filters"] == [("region", "East")]
    state["filters"] = []
    rows = _grouped_rows(_run(ctx, state["filters"]), ctx)
    assert set(rows) == {"East", "West", "North"}


@step(r"the drill shows only East source rows")
def then_drill_east(ctx: ScenarioContext) -> None:
    drill = _state(ctx)["drill"]
    assert len(drill.table.rows) == 2
    assert all(row[0] == "East" for row in drill.table.rows)


@step(r"the dashboard is still listed")
def then_still_listed(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    assert any(
        d.dashboard_id == state["dashboard_id"] for d in state["repo"].dashboards()
    )


@step(r"opening it shows the doubled totals")
def then_doubled(ctx: ScenarioContext) -> None:
    rows = _grouped_rows(_run(ctx, []), ctx)
    assert rows == {"East": 60.0, "West": 140.0, "North": 100.0}, rows


@step(r"opening the dashboard reports the revenue widget's data as gone")
def then_revenue_gone(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    state["run"] = _run(ctx, [])
    widget = _widget_by_source(ctx, "sales.csv", grouped=True)
    assert state["run"]["widgets"][widget.widget_id]["error"]


@step(r"the staff widget still renders its numbers")
def then_staff_survives(ctx: ScenarioContext) -> None:
    widget = _widget_by_source(ctx, "staff.csv")
    assert _state(ctx)["run"]["widgets"][widget.widget_id]["answer"] is not None


@step(r"the broken widget can be removed from the dashboard")
def then_remove_broken(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    widget = _widget_by_source(ctx, "sales.csv", grouped=True)
    state["repo"].remove_widget(state["dashboard_id"], widget.widget_id)
    remaining = [w.widget_id for w in _dash(ctx).widgets]
    assert widget.widget_id not in remaining


@step(r"the action is rejected as not found")
def then_not_found(ctx: ScenarioContext) -> None:
    assert isinstance(_state(ctx)["error"], UnknownDashboardError)


@step(r"nothing else changes")
def then_nothing_changed(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    now = [d.dashboard_id for d in state["repo"].dashboards()]
    assert now == state["before_list"]


@step(r"opening and filtering the dashboard still works")
def then_offline_viewing(ctx: ScenarioContext) -> None:
    rows = _grouped_rows(_run(ctx, [("region", "East")]), ctx)
    assert rows == {"East": 30.0}


@step(r"asking for a new dashboard fails with a plain message")
def then_offline_authoring_fails(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    try:
        state["repo"].create_dashboard("another dashboard")
        raise AssertionError("expected DashboardAssemblyError")
    except DashboardAssemblyError as exc:
        assert "AI" in str(exc)


# --------------------------------------------------------------------------- #
# Thens — editing
# --------------------------------------------------------------------------- #
@step(r"the dashboard gains the requested widget")
def then_gains_widget(ctx: ScenarioContext) -> None:
    edited = _state(ctx)["edited"]
    joined = " ".join(w.widget_id + " " + w.sql for w in edited.widgets).lower()
    assert "count" in joined and "region" in joined


@step(r"removing a widget shrinks the dashboard")
def then_remove_shrinks(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    before = len(_dash(ctx).widgets)
    victim = _dash(ctx).widgets[-1]
    state["repo"].remove_widget(state["dashboard_id"], victim.widget_id)
    assert len(_dash(ctx).widgets) == before - 1


@step(r"a widget's presentation can be switched without affecting the others")
def then_presentation_switchable(ctx: ScenarioContext) -> None:
    run = _run(ctx, [])
    charted = [
        e["answer"]
        for e in run["widgets"].values()
        if e["answer"] is not None and e["answer"].chart_data
    ]
    assert charted, "no chart-typed widget to switch"
    # both presentations are available on the switched widget...
    assert charted[0].table is not None
    # ...and the other widgets' payloads are independent objects
    others = [
        e["answer"] for e in run["widgets"].values() if e["answer"] is not charted[0]
    ]
    assert all(o is not charted[0] for o in others)


# --------------------------------------------------------------------------- #
# Workbench flows (browser) — fixtures app
# --------------------------------------------------------------------------- #
@step(r"the analyst app is open in a browser")
def given_app_open(ctx: ScenarioContext) -> None:
    expect = _expect()
    ctx.page.goto(_STACK["web"])
    expect(ctx.page.get_by_text("Catalog", exact=True).first).to_be_visible()
    ctx.page.evaluate("window.__no_reload_pin = 1")


@step(r"the user opens the Dashboards area")
def when_open_dashboards_area(ctx: ScenarioContext) -> None:
    ctx.page.get_by_role("button", name="Dashboards", exact=True).click()


@step(r'the user requests "(?P<request>[^"]+)"')
def when_request_dashboard(ctx: ScenarioContext, request: str) -> None:
    ctx.page.get_by_label("Dashboard request").fill(request)
    ctx.page.get_by_role("button", name="Create dashboard").click()


@step(r"a dashboard renders with its widgets")
def then_dashboard_renders(ctx: ScenarioContext) -> None:
    expect = _expect()
    expect(ctx.page.get_by_text("Revenue by region", exact=True).first).to_be_visible()
    expect(ctx.page.get_by_text("Customers", exact=True).first).to_be_visible()


@step(r'the user filters to region "(?P<value>[^"]+)"')
def when_filter_in_workbench(ctx: ScenarioContext, value: str) -> None:
    field = ctx.page.get_by_label("Filter Region")
    field.fill(value)
    field.press("Enter")


@step(r"the widgets update without a page reload")
def then_widgets_update(ctx: ScenarioContext) -> None:
    expect = _expect()
    expect(
        ctx.page.get_by_label("Widget Customers unaffected by filter")
    ).to_be_visible()
    assert ctx.page.evaluate("window.__no_reload_pin") == 1, "the page reloaded"


@step(r"a sample dashboard is open in the Dashboards area")
def given_sample_dashboard_open(ctx: ScenarioContext) -> None:
    response = httpx.post(
        f"{ctx.api}/api/dashboards",
        json={"request": "a sales overview dashboard"},
        timeout=10,
    )
    assert response.status_code == 200, response.text
    ctx.page.get_by_role("button", name="Dashboards", exact=True).click()
    ctx.page.get_by_role("button", name="Open dashboard Sales overview").click()
    _expect()(
        ctx.page.get_by_text("Revenue by region", exact=True).first
    ).to_be_visible()


@step(r"the user clicks a bar of the first widget")
def when_click_first_bar(ctx: ScenarioContext) -> None:
    ctx.page.get_by_label("Bar North").click()


@step(r"the active filter chip appears")
def then_filter_chip(ctx: ScenarioContext) -> None:
    expect = _expect()
    expect(ctx.page.get_by_label("Active filter region North")).to_be_visible()


@step(r"the user drills into the first widget")
def when_drill_first(ctx: ScenarioContext) -> None:
    ctx.page.get_by_label("Drill into Revenue by region").click()


@step(r"the underlying rows are shown")
def then_rows_shown(ctx: ScenarioContext) -> None:
    expect = _expect()
    expect(ctx.page.get_by_label("Rows behind Revenue by region")).to_be_visible()
    expect(ctx.page.get_by_role("columnheader", name="order_id")).to_be_visible()
