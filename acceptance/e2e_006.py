"""Step handlers for feature 006 — two-surface workbench UX.

Built on acceptance/e2e_base.py (shared fixtures API + production frontend
build + Chromium), exactly like features 002/003/005:

- AC-3 (the source.entity.ext naming rule) binds over HTTP against a lazily
  booted REAL-store service (ANALYST_FIXTURES=0) — a real Excel workbook and a
  real CSV are ingested and their dataset ids + groups are asserted on the wire.
- Every other scenario drives Chromium via Playwright against the fixtures app.
  The connected-database scenarios connect the bundled Chinook SQLite fixture as
  "sales_db" (real federation, deterministic, offline) so the Databases section
  and the not-yet-queryable marking are exercised without a live DB.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import httpx
import pytest
from openpyxl import Workbook

from acceptance.e2e_base import (
    REPO_ROOT,
    ScenarioContext,
    _e2e_fresh,
    _e2e_stack,
    _free_port,
    _wait_http,
    expect_,
    make_registry,
)

CHINOOK = REPO_ROOT / "tests" / "golden" / "chinook.sqlite"

step, run_step = make_registry()
_expect = expect_

__all__ = [
    "ScenarioContext",
    "run_step",
    "_e2e_stack",
    "_e2e_fresh",
    "_e2e_006_real",
]

_REAL: dict[str, Any] = {}


# --------------------------------------------------------------------------- #
# Lazy REAL-store service — for the AC-3 naming rule over HTTP.
# --------------------------------------------------------------------------- #
def _real_api() -> str:
    if "api" in _REAL:
        return _REAL["api"]
    tmp = Path(tempfile.mkdtemp(prefix="analyst-e2e-006-"))
    port = _free_port()
    api = f"http://127.0.0.1:{port}"
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "analyst.api.app:app",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "ANALYST_FIXTURES": "0",
            "ANALYST_DATA_DIR": str(tmp / "data"),
        },
    )
    _REAL.update(api=api, proc=proc, tmp=tmp)
    _wait_http(f"{api}/api/health")
    return api


@pytest.fixture(scope="session", autouse=True)
def _e2e_006_real():
    yield
    proc = _REAL.pop("proc", None)
    if proc is not None:
        proc.terminate()
        proc.wait(timeout=10)
    _REAL.clear()


def _datasets(api: str) -> list[dict]:
    return httpx.get(f"{api}/api/datasets", timeout=30.0).json()


# --------------------------------------------------------------------------- #
# AC-3 — dataset naming (HTTP, real store)
# --------------------------------------------------------------------------- #
@step(r"a workspace with the seeded datasets")
def given_workspace(ctx: ScenarioContext) -> None:
    api = _real_api()
    assert httpx.get(f"{api}/api/health").json()["ok"] is True


@step(
    r'an Excel file "(?P<file>[^"]+)" with sheets "(?P<a>[^"]+)" and '
    r'"(?P<b>[^"]+)" is ingested'
)
def when_ingest_excel(ctx: ScenarioContext, file: str, a: str, b: str) -> None:
    wb = Workbook()
    first = wb.active
    first.title = a
    first.append(["id", "name"])
    first.append([1, "alice"])
    second = wb.create_sheet(b)
    second.append(["id", "label"])
    second.append([1, "sales"])
    path = ctx.tmp_path / file
    wb.save(path)
    with path.open("rb") as handle:
        ctx.response = httpx.post(
            f"{_real_api()}/api/datasets/ingest",
            files={"file": (file, handle.read())},
            timeout=30.0,
        )
    assert ctx.response.status_code == 200, ctx.response.text


@step(r'the datasets "(?P<a>[^"]+)" and "(?P<b>[^"]+)" exist')
def then_datasets_exist(ctx: ScenarioContext, a: str, b: str) -> None:
    names = {d["name"] for d in _datasets(_real_api())}
    assert {a, b} <= names, f"missing {{{a}, {b}}} from {names}"


@step(r'they share the group "(?P<group>[^"]+)"')
def then_share_group(ctx: ScenarioContext, group: str) -> None:
    groups = {
        d["name"]: d["group"] for d in _datasets(_real_api()) if d["group"] == group
    }
    assert len(groups) >= 2, f"expected >=2 datasets in group {group!r}, got {groups}"


@step(r'a CSV file "(?P<file>[^"]+)" is ingested')
def when_ingest_csv(ctx: ScenarioContext, file: str) -> None:
    ctx.response = httpx.post(
        f"{_real_api()}/api/datasets/ingest",
        files={"file": (file, b"id,amount\n1,10\n2,20\n")},
        timeout=30.0,
    )
    assert ctx.response.status_code == 200, ctx.response.text


@step(r'the dataset "(?P<name>[^"]+)" exists')
def then_dataset_exists(ctx: ScenarioContext, name: str) -> None:
    names = {d["name"] for d in _datasets(_real_api())}
    assert name in names, f"{name!r} not in {names}"


@step(r'its group is "(?P<group>[^"]+)" with one table')
def then_group_of_one(ctx: ScenarioContext, group: str) -> None:
    members = [d["name"] for d in _datasets(_real_api()) if d["group"] == group]
    assert len(members) == 1, f"expected one table in group {group!r}, got {members}"


# --------------------------------------------------------------------------- #
# Browser helpers
# --------------------------------------------------------------------------- #
def _db_path(ctx: ScenarioContext) -> str:
    dest = ctx.tmp_path / "sales_db.sqlite"
    if not dest.exists():
        shutil.copy(CHINOOK, dest)
    return str(dest)


def _connect_sales_db_http(ctx: ScenarioContext) -> None:
    resp = httpx.post(
        f"{ctx.api}/api/databases/connect",
        json={"name": "sales_db", "engine": "sqlite", "path": _db_path(ctx)},
        timeout=30.0,
    )
    assert resp.status_code == 201, resp.text


def _open_workbench(ctx: ScenarioContext) -> None:
    ctx.page.goto(ctx.web)
    _expect()(ctx.page.get_by_text("Semantic catalog").first).to_be_visible()


# --------------------------------------------------------------------------- #
# Givens
# --------------------------------------------------------------------------- #
@step(r"the app is open on the Ingest & Profile view")
def given_app_on_ingest(ctx: ScenarioContext) -> None:
    _open_workbench(ctx)


@step(r"the app is open on the Ingest & Profile view with a connected database")
def given_app_on_ingest_with_db(ctx: ScenarioContext) -> None:
    _connect_sales_db_http(ctx)
    _open_workbench(ctx)


@step(r"the app is open in a browser")
def given_app_open(ctx: ScenarioContext) -> None:
    _open_workbench(ctx)


@step(r"the app is open on the Query view")
def given_app_on_query(ctx: ScenarioContext) -> None:
    _open_workbench(ctx)
    ctx.page.get_by_role("button", name="Query").click()
    _expect()(ctx.page.get_by_placeholder("Ask across all tables")).to_be_visible()


# --------------------------------------------------------------------------- #
# AC-1 — add data
# --------------------------------------------------------------------------- #
@step(r"the view invites the user to upload a file")
def then_upload_invite(ctx: ScenarioContext) -> None:
    _expect()(ctx.page.get_by_text("Drop a file, or click to upload")).to_be_visible()


@step(r"the view offers to connect a database")
def then_connect_offer(ctx: ScenarioContext) -> None:
    _expect()(ctx.page.get_by_role("button", name="Connect a database")).to_be_visible()


@step(r'the user connects the fixture database "(?P<name>[^"]+)"')
def when_connect_fixture_db(ctx: ScenarioContext, name: str) -> None:
    ctx.page.get_by_role("button", name="Connect a database").click()
    ctx.page.get_by_label("Connection name").fill(name)
    ctx.page.get_by_label("Database engine").select_option("sqlite")
    ctx.page.get_by_label("Database file path").fill(_db_path(ctx))
    ctx.page.get_by_role("button", name="Connect database").click()


@step(r'"(?P<name>[^"]+)" appears in the Databases section')
def then_db_in_section(ctx: ScenarioContext, name: str) -> None:
    _expect()(
        ctx.page.get_by_role("button", name=f"Detach database {name}")
    ).to_be_visible(timeout=20_000)


# --------------------------------------------------------------------------- #
# AC-2 — the two sections + expandability
# --------------------------------------------------------------------------- #
@step(r'the left rail shows a "Files" section and a "Databases" section')
def then_two_sections(ctx: ScenarioContext) -> None:
    expect = _expect()
    expect(ctx.page.get_by_text("Files", exact=True).first).to_be_visible()
    expect(ctx.page.get_by_text("Databases", exact=True).first).to_be_visible()


@step(r"each source can be expanded to its tables and each table to its columns")
def then_expandable(ctx: ScenarioContext) -> None:
    expect = _expect()
    # A file table is listed (source -> table) ...
    expect(ctx.page.get_by_text("sales.csv").first).to_be_visible()
    # ... and expands to its columns.
    ctx.page.get_by_role("button", name="Toggle columns of sales.csv").first.click()
    expect(ctx.page.get_by_text("order_id").first).to_be_visible()


# --------------------------------------------------------------------------- #
# AC-4/5/6/12 — selecting a table / column
# --------------------------------------------------------------------------- #
@step(r'the user selects the table "(?P<name>[^"]+)"')
def when_select_table(ctx: ScenarioContext, name: str) -> None:
    ctx.page.get_by_role("button", name=f"Open table {name}").first.click()


@step(r"each column's inferred type and null rate are shown")
def then_columns_type_and_null(ctx: ScenarioContext) -> None:
    expect = _expect()
    expect(ctx.page.get_by_text("order_id").first).to_be_visible()
    expect(ctx.page.get_by_text("null", exact=False).first).to_be_visible()


@step(r"the table's plain-English description is shown")
def then_table_description(ctx: ScenarioContext) -> None:
    description = httpx.get(f"{ctx.api}/api/catalog").json()["sales"][
        "tableDescription"
    ]
    _expect()(ctx.page.get_by_text(description).first).to_be_visible()


@step(r"each column's description and role are shown")
def then_column_desc_and_role(ctx: ScenarioContext) -> None:
    expect = _expect()
    first = httpx.get(f"{ctx.api}/api/catalog").json()["sales"]["columns"][0]
    expect(ctx.page.get_by_text(first["description"]).first).to_be_visible()
    expect(ctx.page.get_by_text("ID", exact=True).first).to_be_visible()


@step(r'the user selects a column of "(?P<name>[^"]+)"')
def when_select_column(ctx: ScenarioContext, name: str) -> None:
    ctx.page.get_by_role("button", name=f"Open table {name}").first.click()
    ctx.page.get_by_role("button", name="Column order_id").first.click()


@step(r"the column drilldown shows its profile and its semantic description")
def then_drilldown(ctx: ScenarioContext) -> None:
    expect = _expect()
    expect(ctx.page.get_by_text("Column drilldown").first).to_be_visible()
    expect(ctx.page.get_by_text("Distinct").first).to_be_visible()
    description = httpx.get(f"{ctx.api}/api/catalog").json()["sales"]["columns"]
    order_id = next(c for c in description if c["name"] == "order_id")
    expect(ctx.page.get_by_text(order_id["description"]).first).to_be_visible()


@step(r"the semantic descriptions are shown without an edit control")
def then_read_only(ctx: ScenarioContext) -> None:
    expect = _expect()
    description = httpx.get(f"{ctx.api}/api/catalog").json()["sales"][
        "tableDescription"
    ]
    expect(ctx.page.get_by_text(description).first).to_be_visible()
    # Read-only: no edit affordance and no editable field in the detail.
    expect(ctx.page.get_by_role("button", name="Edit")).to_have_count(0)
    expect(ctx.page.get_by_role("textbox")).to_have_count(0)


# --------------------------------------------------------------------------- #
# AC-7/8 — connected database tables
# --------------------------------------------------------------------------- #
@step(r'the user expands the database "(?P<name>[^"]+)"')
def when_expand_database(ctx: ScenarioContext, name: str) -> None:
    # Groups render open; open a connected table's detail to reveal its profile.
    _expect()(
        ctx.page.get_by_role("button", name=f"Open table {name}.Album")
    ).to_be_visible(timeout=20_000)
    ctx.page.get_by_role("button", name=f"Open table {name}.Album").first.click()


@step(r"its tables are listed with profiles")
def then_db_tables_profiled(ctx: ScenarioContext) -> None:
    expect = _expect()
    expect(ctx.page.get_by_text("sales_db.Album").first).to_be_visible()
    # the opened detail reports a profile (row/column count line)
    expect(ctx.page.get_by_text("columns", exact=False).first).to_be_visible()


@step(r"they are marked as not yet answerable by Q&A")
def then_not_answerable(ctx: ScenarioContext) -> None:
    _expect()(ctx.page.get_by_text("Not yet answerable by Q&A").first).to_be_visible()


@step(r'the user disconnects the database "(?P<name>[^"]+)"')
def when_disconnect_db(ctx: ScenarioContext, name: str) -> None:
    ctx.page.get_by_role("button", name=f"Detach database {name}").click()


@step(r'"(?P<name>[^"]+)" no longer appears in the Databases section')
def then_db_gone(ctx: ScenarioContext, name: str) -> None:
    expect = _expect()
    expect(
        ctx.page.get_by_role("button", name=f"Detach database {name}")
    ).to_have_count(0)
    expect(ctx.page.get_by_text(f"{name}.Album")).to_have_count(0)


# --------------------------------------------------------------------------- #
# AC-9/10/11 — the Query surface
# --------------------------------------------------------------------------- #
@step(r"the user opens the Query view")
def when_open_query(ctx: ScenarioContext) -> None:
    ctx.page.get_by_role("button", name="Query").click()


@step(r"the Q&A conversation is shown")
def then_conversation_shown(ctx: ScenarioContext) -> None:
    _expect()(ctx.page.get_by_placeholder("Ask across all tables")).to_be_visible()


@step(r"no catalog tree or metadata panel is shown")
def then_no_catalog(ctx: ScenarioContext) -> None:
    # The source-grouped catalog tree (its table rows) and the connect-a-database
    # metadata affordance live only on the workbench — never on Query.
    expect = _expect()
    expect(ctx.page.get_by_text("sales.csv")).to_have_count(0)
    expect(ctx.page.get_by_role("button", name="Connect a database")).to_have_count(0)


@step(r"the user opens the Ingest & Profile view")
def when_open_ingest(ctx: ScenarioContext) -> None:
    ctx.page.get_by_role("button", name="Ingest & profile").click()


@step(r"the upload zone is shown")
def then_upload_zone(ctx: ScenarioContext) -> None:
    _expect()(ctx.page.get_by_text("Drop a file, or click to upload")).to_be_visible()


@step(r'the user asks "(?P<question>[^"]+)"')
def when_user_asks(ctx: ScenarioContext, question: str) -> None:
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


@step(r"an answer appears with its trust trail")
def then_answer_with_trail(ctx: ScenarioContext) -> None:
    _expect()(ctx.page.get_by_text("Trust trail").first).to_be_visible()
