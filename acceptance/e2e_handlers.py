"""Step handlers for feature 002 — GWT bound to HTTP + a real browser.

Same DAE acceptance pipeline as feature 001 (spec.md -> IR -> generated pytest),
but the binding layer differs: API-contract steps drive the running FastAPI
service over HTTP (httpx); frontend-flow steps drive Chromium via Playwright
against the PRODUCTION build (vite preview), proxied to the same service.

Shared infrastructure (session stack, registry, isolation) lives in
acceptance/e2e_base.py — new features create their own e2e_<slug>.py on the
same base instead of editing this file.
"""

from __future__ import annotations

import httpx

from acceptance.e2e_base import (
    _STACK,
    ScenarioContext,
    _e2e_fresh,
    _e2e_stack,
    expect_,
    make_registry,
)

CSV = "id,amount\n1,10\n2,20\n"

step, run_step = make_registry()
_expect = expect_

__all__ = ["ScenarioContext", "run_step", "_e2e_stack", "_e2e_fresh"]


# --------------------------------------------------------------------------- #
# API-contract steps (AC-1..AC-5) — HTTP against the fixtures API
# --------------------------------------------------------------------------- #
@step(r"the analyst service is running with mocked data")
def given_service_running(ctx: ScenarioContext) -> None:
    health = httpx.get(f"{ctx.api}/api/health").json()
    assert health["ok"] is True and health["fixtures"] is True


@step(r"a client lists the datasets")
def when_list_datasets(ctx: ScenarioContext) -> None:
    ctx.response = httpx.get(f"{ctx.api}/api/datasets")
    ctx.data = ctx.response.json()


@step(r'the datasets "sales", "customers" and "products" are returned')
def then_seeded_datasets(ctx: ScenarioContext) -> None:
    assert {d["name"] for d in ctx.data} == {"sales", "customers", "products"}


@step(r"each dataset carries its column profiles and catalog descriptions")
def then_profiles_and_catalog(ctx: ScenarioContext) -> None:
    for ds in ctx.data:
        assert ds["profile"]["columns"], f"{ds['name']} has no profile columns"
        assert ds["catalog"]["tableDescription"], f"{ds['name']} has no catalog"


@step(r"a client checks the service health")
def when_check_health(ctx: ScenarioContext) -> None:
    ctx.data = httpx.get(f"{ctx.api}/api/health").json()


@step(r"the service reports that mocked data is in use")
def then_mocked_mode(ctx: ScenarioContext) -> None:
    assert ctx.data["fixtures"] is True


@step(r'a client refreshes "sales" with a conforming file')
def when_refresh_sales(ctx: ScenarioContext) -> None:
    ctx.data = httpx.post(
        f"{ctx.api}/api/datasets/sales/refresh",
        files={"file": ("sales.csv", CSV.encode())},
    ).json()


@step(r"the refresh is accepted as a new version")
def then_refresh_versioned(ctx: ScenarioContext) -> None:
    assert ctx.data["replaced"] is True and ctx.data["version"] == 2


@step(r'a client deletes the dataset "customers"')
def when_delete_customers(ctx: ScenarioContext) -> None:
    assert httpx.delete(f"{ctx.api}/api/datasets/customers").status_code == 204


@step(r'"customers" is no longer listed')
def then_customers_gone(ctx: ScenarioContext) -> None:
    names = {d["name"] for d in httpx.get(f"{ctx.api}/api/datasets").json()}
    assert "customers" not in names


@step(r'a client requests the dataset "nope"')
def when_request_unknown(ctx: ScenarioContext) -> None:
    ctx.response = httpx.get(f"{ctx.api}/api/datasets/nope")


@step(r'the service answers not-found, naming "nope"')
def then_not_found(ctx: ScenarioContext) -> None:
    assert ctx.response is not None and ctx.response.status_code == 404
    assert "nope" in ctx.response.json()["detail"]


@step(r'a client asks "What is the average order value\?"')
def when_ask_aov(ctx: ScenarioContext) -> None:
    ctx.data = httpx.post(
        f"{ctx.api}/api/query",
        json={"question": "What is the average order value?"},
    ).json()


@step(r"an answer is returned with a summary and a trust trail")
def then_answer_with_trail(ctx: ScenarioContext) -> None:
    assert ctx.data["type"] == "answer" and ctx.data["summary"]
    trail = ctx.data["trustTrail"]
    assert trail["assumptions"] and trail["lineage"] and trail["sql"]


# --------------------------------------------------------------------------- #
# Frontend-flow steps (AC-6..AC-11) — Playwright against the built app
# --------------------------------------------------------------------------- #
@step(r"the analyst app is open in a browser")
def given_app_open(ctx: ScenarioContext) -> None:
    expect = _expect()
    ctx.page.goto(_STACK["web"])
    expect(ctx.page.get_by_text("Catalog", exact=True).first).to_be_visible()


@step(r"the analyst app is open on the ingestion view")
def given_app_on_ingestion(ctx: ScenarioContext) -> None:
    given_app_open(ctx)
    ctx.page.get_by_role("button", name="Ingest & profile").click()
    _expect()(ctx.page.get_by_role("button", name="Add data")).to_be_visible()


@step(r'the semantic catalog lists "sales", "customers" and "products"')
def then_catalog_lists_seeded(ctx: ScenarioContext) -> None:
    expect = _expect()
    for name in ("sales", "customers", "products"):
        expect(
            ctx.page.get_by_role("button", name=f"Open table {name}").first
        ).to_be_visible()


@step(r'the table details describe the dataset "sales" in plain English')
def then_details_describe_sales(ctx: ScenarioContext) -> None:
    description = httpx.get(f"{ctx.api}/api/catalog").json()["sales"][
        "tableDescription"
    ]
    _expect()(ctx.page.get_by_text(description).first).to_be_visible()


@step(r'the table details show the row count "143,209 rows"')
def then_details_row_count(ctx: ScenarioContext) -> None:
    _expect()(ctx.page.get_by_text("143,209 rows")).to_be_visible()


@step(r"the columns are described in plain English with their roles")
def then_columns_described(ctx: ScenarioContext) -> None:
    expect = _expect()
    first = httpx.get(f"{ctx.api}/api/catalog").json()["sales"]["columns"][0]
    expect(ctx.page.get_by_text(first["description"]).first).to_be_visible()
    expect(ctx.page.get_by_text("ID", exact=True).first).to_be_visible()


@step(r'the user asks "(?P<question>[^"]+)"')
def when_user_asks(ctx: ScenarioContext, question: str) -> None:
    # Feature 006: Q&A now lives on the dedicated Query surface; switch to it
    # before asking (the app opens on the Ingest & Profile workbench).
    ctx.page.get_by_role("button", name="Query").click()
    box = ctx.page.get_by_placeholder("Ask across all tables")
    box.fill(question)
    box.press("Enter")


@step(r"the agent asks which region column to use")
def then_agent_clarifies(ctx: ScenarioContext) -> None:
    expect = _expect()
    expect(ctx.page.get_by_text("AskQuestion").first).to_be_visible()
    expect(
        ctx.page.get_by_text("Two region columns are available.", exact=False)
    ).to_be_visible()


@step(r"the user chooses the customer region option")
def when_choose_customer_region(ctx: ScenarioContext) -> None:
    ctx.page.get_by_role("button").filter(has_text="customer region").click()


@step(r"an answer appears summarising revenue by region")
def then_revenue_answer(ctx: ScenarioContext) -> None:
    _expect()(
        ctx.page.get_by_text("East region generated the most", exact=False)
    ).to_be_visible()


@step(r"the user switches the answer to the table view")
def when_switch_to_table(ctx: ScenarioContext) -> None:
    _expect()(
        ctx.page.get_by_text("East region generated the most", exact=False)
    ).to_be_visible()
    ctx.page.get_by_role("button", name="Table", exact=True).click()


@step(r"the result table is shown with a CSV download")
def then_result_table_shown(ctx: ScenarioContext) -> None:
    expect = _expect()
    expect(ctx.page.get_by_role("columnheader", name="region")).to_be_visible()
    expect(ctx.page.get_by_role("button", name="Download CSV")).to_be_visible()


@step(r"the trust trail reveals assumptions, lineage and SQL")
def then_trust_trail(ctx: ScenarioContext) -> None:
    expect = _expect()
    expect(ctx.page.get_by_text("Trust trail").first).to_be_visible()
    expect(
        ctx.page.get_by_text("Revenue is calculated", exact=False).first
    ).to_be_visible()
    ctx.page.get_by_role("button", name="Lineage", exact=True).click()
    expect(ctx.page.get_by_text("ds-sales-001", exact=False).first).to_be_visible()
    ctx.page.get_by_role("button", name="SQL", exact=True).click()
    expect(ctx.page.locator("pre").first).to_be_visible()


@step(r"the user drops a file on the upload zone")
def when_drop_file(ctx: ScenarioContext) -> None:
    # Open the add-data menu, then set the file on its hidden input (the REAL
    # file is what gets uploaded).
    ctx.page.get_by_role("button", name="Add data").click()
    ctx.page.get_by_label("Choose a file to upload").set_input_files(
        files=[
            {
                "name": "transactions_q4.csv",
                "mimeType": "text/csv",
                "buffer": CSV.encode(),
            }
        ]
    )


@step(r"the upload progresses to completion")
def then_upload_completes(ctx: ScenarioContext) -> None:
    _expect()(
        ctx.page.get_by_role("button", name="Open table transactions").first
    ).to_be_visible(timeout=20_000)


@step(r'"transactions" appears among the ingested datasets')
def then_upload_listed(ctx: ScenarioContext) -> None:
    _expect()(
        ctx.page.get_by_role("button", name="Open table transactions").first
    ).to_be_visible()


@step(r"the user opens the ingestion view")
def when_open_ingestion(ctx: ScenarioContext) -> None:
    ctx.page.get_by_role("button", name="Ingest & profile").click()


@step(r"the upload zone invites them to drop a file")
def then_upload_zone_visible(ctx: ScenarioContext) -> None:
    _expect()(ctx.page.get_by_role("button", name="Add data")).to_be_visible()


@step(r"the user opens the workspace view")
def when_open_workspace(ctx: ScenarioContext) -> None:
    # Feature 006: the "Catalog & Q&A" tab is renamed to "Query".
    ctx.page.get_by_role("button", name="Query").click()


@step(r"the Q&A panel invites them to ask a question")
def then_qa_panel_visible(ctx: ScenarioContext) -> None:
    _expect()(ctx.page.get_by_placeholder("Ask across all tables")).to_be_visible()


@step(r'the user deletes the dataset "sales"')
def when_delete_sales_ui(ctx: ScenarioContext) -> None:
    ctx.page.get_by_role("button", name="Delete dataset sales").click()
    ctx.page.get_by_role("button", name="Confirm delete sales").click()


@step(r'"sales.csv" no longer appears in the semantic catalog')
def then_sales_gone_from_catalog(ctx: ScenarioContext) -> None:
    _expect()(ctx.page.get_by_text("sales.csv")).to_have_count(0)


# --------------------------------------------------------------------------- #
# Defect regressions (exploratory 2026-07-02) — AC-12 (API) + AC-13 (UI)
# --------------------------------------------------------------------------- #
@step(r"a client ingests an empty file")
def when_ingest_empty_file(ctx: ScenarioContext) -> None:
    ctx.response = httpx.post(
        f"{ctx.api}/api/datasets/ingest", files={"file": ("empty.csv", b"")}
    )


@step(r"the ingestion is rejected as a client error with a clear message")
def then_rejected_client_error(ctx: ScenarioContext) -> None:
    assert ctx.response is not None
    assert 400 <= ctx.response.status_code < 500, (
        f"expected a 4xx rejection, got {ctx.response.status_code}"
    )
    assert "empty" in ctx.response.json()["detail"].lower()


@step(r"no server error occurs")
def then_no_server_error(ctx: ScenarioContext) -> None:
    assert ctx.response is not None and ctx.response.status_code < 500


@step(r"the user uploads an empty file")
def when_upload_empty_file(ctx: ScenarioContext) -> None:
    ctx.page.get_by_role("button", name="Add data").click()
    ctx.page.get_by_label("Choose a file to upload").set_input_files(
        files=[{"name": "empty.csv", "mimeType": "text/csv", "buffer": b""}]
    )


@step(r"the upload is marked failed")
def then_upload_marked_failed(ctx: ScenarioContext) -> None:
    _expect()(ctx.page.get_by_text("Failed", exact=True).first).to_be_visible()


@step(r"the failure reason mentions the file is empty")
def then_failure_reason_shown(ctx: ScenarioContext) -> None:
    _expect()(
        ctx.page.get_by_text("The file is empty", exact=False).first
    ).to_be_visible()
