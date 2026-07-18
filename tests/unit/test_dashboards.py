"""Feature 015 — dashboards: filter machinery, run/drill, persistence."""

from __future__ import annotations

import pytest

from analyst.api.repository import StoreRepository
from analyst.domain.dashboards import (
    Dashboard,
    DashboardFilter,
    DashboardWidget,
    UnknownDashboardError,
)
from analyst.engine.dashboards import (
    InvalidWidgetSQLError,
    apply_filters,
    validate_widget_sql,
)

SALES = (
    "region,product,amount\n"
    "East,widget,10\nEast,gadget,20\nWest,widget,30\n"
    "West,gadget,40\nNorth,widget,50\n"
)
STAFF = "employee,dept\nAna,ops\nBo,sales\n"

REVENUE_SQL = (
    'SELECT region, SUM(amount) AS total FROM "sales.csv" '
    "WHERE /*FILTERS*/ 1=1 GROUP BY region ORDER BY total DESC"
)
HEADCOUNT_SQL = 'SELECT COUNT(*) AS n FROM "staff.csv" WHERE /*FILTERS*/ 1=1'


def _dashboard() -> Dashboard:
    return Dashboard(
        dashboard_id="sales-overview",
        name="Sales overview",
        widgets=(
            DashboardWidget(
                widget_id="revenue-by-region",
                question="Revenue by region",
                sql=REVENUE_SQL,
                chart_type="bar",
                title="Revenue by region",
                source="sales.csv",
            ),
            DashboardWidget(
                widget_id="headcount",
                question="How many staff?",
                sql=HEADCOUNT_SQL,
                chart_type="stat",
                title="Headcount",
                source="staff.csv",
            ),
        ),
        filters=(DashboardFilter(column="region", label="Region"),),
    )


def _repo(tmp_path) -> StoreRepository:
    repo = StoreRepository(str(tmp_path / "data"))
    repo.ingest("sales.csv", SALES.encode())
    repo.ingest("staff.csv", STAFF.encode())
    return repo


# --------------------------------------------------------------------------- #
# Filter machinery (engine)
# --------------------------------------------------------------------------- #
def test_marker_is_required():
    with pytest.raises(InvalidWidgetSQLError):
        validate_widget_sql('SELECT * FROM "sales.csv"')
    validate_widget_sql(REVENUE_SQL)  # no raise


def test_filters_substitute_before_aggregation():
    sql = apply_filters(REVENUE_SQL, [("region", "East")])
    assert "\"region\" = 'East'" in sql and "/*FILTERS*/" not in sql


def test_filter_values_are_escaped_and_still_guarded():
    sql = apply_filters(REVENUE_SQL, [("region", "Ea'st'); DROP TABLE x;--")])
    assert "''" in sql  # quote doubling
    assert "DROP" in sql  # inert inside the string literal
    assert sql.count("'") % 2 == 0


def test_no_filters_yields_clean_sql():
    assert "1=1" in apply_filters(REVENUE_SQL, [])


# --------------------------------------------------------------------------- #
# Repository: run / drill / persistence / broken widgets
# --------------------------------------------------------------------------- #
def test_run_dashboard_unfiltered_and_filtered(tmp_path):
    repo = _repo(tmp_path)
    repo.put_dashboard(_dashboard())
    results = repo.run_dashboard("sales-overview", [])
    revenue = results["widgets"]["revenue-by-region"]["answer"]
    assert {r[0]: r[1] for r in revenue.table.rows} == {
        "East": 30.0,
        "West": 70.0,
        "North": 50.0,
    }
    filtered = repo.run_dashboard("sales-overview", [("region", "East")])
    revenue = filtered["widgets"]["revenue-by-region"]["answer"]
    assert {r[0]: r[1] for r in revenue.table.rows} == {"East": 30.0}


def test_widget_without_the_dimension_is_unaffected(tmp_path):
    repo = _repo(tmp_path)
    repo.put_dashboard(_dashboard())
    filtered = repo.run_dashboard("sales-overview", [("region", "East")])
    headcount = filtered["widgets"]["headcount"]
    assert headcount["unaffected_by"] == ["region"]
    assert headcount["answer"].stat.value == "2"


def test_drill_returns_filtered_source_rows(tmp_path):
    repo = _repo(tmp_path)
    repo.put_dashboard(_dashboard())
    drill = repo.drill_dashboard(
        "sales-overview", "revenue-by-region", [("region", "East")]
    )
    assert len(drill.table.rows) == 2
    assert all(row[0] == "East" for row in drill.table.rows)


def test_dashboards_persist_across_restart(tmp_path):
    repo = _repo(tmp_path)
    repo.put_dashboard(_dashboard())
    reborn = StoreRepository(str(tmp_path / "data"))
    assert [d.name for d in reborn.dashboards()] == ["Sales overview"]
    results = reborn.run_dashboard("sales-overview", [])
    assert results["widgets"]["revenue-by-region"]["answer"] is not None


def test_broken_widget_fails_alone(tmp_path):
    repo = _repo(tmp_path)
    repo.put_dashboard(_dashboard())
    repo.delete("sales.csv")
    results = repo.run_dashboard("sales-overview", [])
    assert results["widgets"]["revenue-by-region"]["error"]
    assert results["widgets"]["headcount"]["answer"] is not None
    repo.delete_dashboard("sales-overview")
    assert repo.dashboards() == []


def test_unknown_dashboard_actions_fail_cleanly(tmp_path):
    repo = _repo(tmp_path)
    with pytest.raises(UnknownDashboardError):
        repo.run_dashboard("nope", [])
    with pytest.raises(UnknownDashboardError):
        repo.delete_dashboard("nope")


# --------------------------------------------------------------------------- #
# Assembly: create/edit/clarify/reject/offline
# --------------------------------------------------------------------------- #
from analyst.agentic.dashboards import (  # noqa: E402
    AssemblyResult,
    ClarificationSpec,
    DashboardAssemblyError,
    FilterSpec,
    WidgetSpec,
)


class StubAssembler:
    def __init__(self, result: AssemblyResult):
        self.result = result
        self.calls: list = []

    def assemble(self, request, tables, current_spec=None):
        self.calls.append({"request": request, "current": current_spec})
        return self.result


GOOD_SPEC = AssemblyResult(
    name="Sales overview",
    widgets=[
        WidgetSpec(
            question="Revenue by region",
            sql=REVENUE_SQL,
            chart_type="bar",
            title="Revenue by region",
            source="sales.csv",
        ),
        WidgetSpec(
            question="How many staff?",
            sql=HEADCOUNT_SQL,
            chart_type="stat",
            title="Headcount",
            source="staff.csv",
        ),
    ],
    filters=[FilterSpec(column="region", label="Region")],
)


def test_create_dashboard_from_spec(tmp_path):
    repo = _repo(tmp_path)
    repo.assembler = StubAssembler(GOOD_SPEC)
    out = repo.create_dashboard("a sales overview dashboard")
    assert out["clarification"] is None
    assert out["dashboard"].dashboard_id == "sales-overview"
    assert [w.widget_id for w in out["dashboard"].widgets] == [
        "revenue-by-region",
        "headcount",
    ]
    assert [d.name for d in repo.dashboards()] == ["Sales overview"]


def test_vague_request_passes_the_clarification_through(tmp_path):
    repo = _repo(tmp_path)
    repo.assembler = StubAssembler(
        AssemblyResult(
            clarification=ClarificationSpec(
                question="Which performance?", options=["Sales", "Staff"]
            )
        )
    )
    out = repo.create_dashboard("a dashboard about performance")
    assert out["dashboard"] is None
    assert out["clarification"].question == "Which performance?"
    assert repo.dashboards() == []


def test_malformed_spec_is_rejected_whole(tmp_path):
    repo = _repo(tmp_path)
    bad = AssemblyResult(
        name="Broken",
        widgets=[
            WidgetSpec(question="ok", sql=REVENUE_SQL, title="Ok", source="sales.csv"),
            WidgetSpec(  # no marker -> invalid
                question="bad",
                sql='SELECT * FROM "sales.csv"',
                title="Bad",
                source="sales.csv",
            ),
        ],
    )
    repo.assembler = StubAssembler(bad)
    with pytest.raises((ValueError,)):
        repo.create_dashboard("anything")
    assert repo.dashboards() == []


def test_offline_authoring_fails_plainly_but_viewing_works(tmp_path):
    repo = _repo(tmp_path)
    repo.put_dashboard(_dashboard())
    assert repo.assembler is None
    with pytest.raises(DashboardAssemblyError) as err:
        repo.create_dashboard("another dashboard")
    assert "AI" in str(err.value)
    assert repo.run_dashboard("sales-overview", [])["widgets"]


def test_edit_replaces_in_place_with_current_spec_in_view(tmp_path):
    repo = _repo(tmp_path)
    repo.assembler = StubAssembler(GOOD_SPEC)
    repo.create_dashboard("a sales overview dashboard")
    extended = AssemblyResult(
        name="Sales overview",
        widgets=list(GOOD_SPEC.widgets)
        + [
            WidgetSpec(
                question="Rows by region",
                sql='SELECT region, COUNT(*) AS n FROM "sales.csv" WHERE /*FILTERS*/ 1=1 GROUP BY region',
                chart_type="bar",
                title="Rows by region",
                source="sales.csv",
            )
        ],
        filters=GOOD_SPEC.filters,
    )
    stub = StubAssembler(extended)
    repo.assembler = stub
    out = repo.edit_dashboard(
        "sales-overview", "add a widget showing the row count by region"
    )
    assert len(out["dashboard"].widgets) == 3
    assert stub.calls[0]["current"] is not None
    assert len(repo.dashboards()) == 1
