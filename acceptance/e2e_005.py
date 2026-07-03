"""Step handlers for feature 005 — database federation, HTTP + browser bound.

Built on acceptance/e2e_base.py (same session stack as feature 002): the
fixtures API + the production frontend build + Chromium. The "sample
relational database" is the bundled Chinook SQLite fixture, copied per
scenario into tmp_path — real federation, deterministic and offline.
"""

from __future__ import annotations

import json
import shutil

import httpx

from acceptance.e2e_base import (
    REPO_ROOT,
    ScenarioContext,
    _e2e_fresh,
    _e2e_stack,
    expect_,
    make_registry,
)

CHINOOK = REPO_ROOT / "tests" / "golden" / "chinook.sqlite"

step, run_step = make_registry()
_expect = expect_

__all__ = ["ScenarioContext", "run_step", "_e2e_stack", "_e2e_fresh"]


def _db_path(ctx: ScenarioContext) -> str:
    return str(ctx.tmp_path / "chinook.sqlite")


def _connect_payload(ctx: ScenarioContext, name: str, **extra: str) -> dict:
    return {"name": name, "engine": "sqlite", "path": _db_path(ctx), **extra}


# --------------------------------------------------------------------------- #
# Shared givens
# --------------------------------------------------------------------------- #
@step(r"the analyst service is running with mocked data")
def given_service_running(ctx: ScenarioContext) -> None:
    health = httpx.get(f"{ctx.api}/api/health").json()
    assert health["ok"] is True and health["fixtures"] is True


@step(r"a sample relational database is available")
def given_sample_database(ctx: ScenarioContext) -> None:
    shutil.copy(CHINOOK, _db_path(ctx))


# --------------------------------------------------------------------------- #
# API-contract steps (AC-1..AC-8)
# --------------------------------------------------------------------------- #
@step(r'a client connects the sample database as "(?P<name>[^"]+)"')
def when_connect(ctx: ScenarioContext, name: str) -> None:
    ctx.response = httpx.post(
        f"{ctx.api}/api/databases/connect",
        json=_connect_payload(ctx, name),
        timeout=30.0,
    )


@step(r'a client connects the sample database as "(?P<name>[^"]+)" sending a password')
def when_connect_with_password(ctx: ScenarioContext, name: str) -> None:
    ctx.data = {"secret": "s3cret-hunter2"}
    ctx.response = httpx.post(
        f"{ctx.api}/api/databases/connect",
        json=_connect_payload(ctx, name, password="s3cret-hunter2"),
        timeout=30.0,
    )


@step(r'the connection "(?P<name>[^"]+)" is listed with its engine and tables')
def then_connection_listed(ctx: ScenarioContext, name: str) -> None:
    assert ctx.response is not None and ctx.response.status_code == 201, (
        f"connect failed: {ctx.response.status_code if ctx.response else '?'} "
        f"{ctx.response.text if ctx.response else ''}"
    )
    listed = httpx.get(f"{ctx.api}/api/databases").json()
    match = next((c for c in listed if c["name"] == name), None)
    assert match is not None, f"'{name}' not in {[c['name'] for c in listed]}"
    assert match["engine"] == "sqlite" and match["tables"]


@step(r'the tables "Album", "Artist" and "Track" appear among the datasets')
def then_tables_are_datasets(ctx: ScenarioContext) -> None:
    names = {d["name"] for d in httpx.get(f"{ctx.api}/api/datasets").json()}
    expected = {"chinook.Album", "chinook.Artist", "chinook.Track"}
    assert expected <= names, f"missing {expected - names}"


@step(r'the dataset "(?P<name>[^"]+)" reports its row count and column profiles')
def then_dataset_profiled(ctx: ScenarioContext, name: str) -> None:
    ds = httpx.get(f"{ctx.api}/api/datasets/{name}").json()
    assert ds["rowCount"] > 0, f"{name} has no rows"
    assert ds["profile"]["columns"], f"{name} has no column profiles"
    first = ds["profile"]["columns"][0]
    assert first["inferredType"] and "distinctCount" in first


@step(r'the dataset "(?P<name>[^"]+)" carries a plain-English catalog entry')
def then_dataset_catalogued(ctx: ScenarioContext, name: str) -> None:
    ds = httpx.get(f"{ctx.api}/api/datasets/{name}").json()
    assert ds["catalog"] is not None, f"{name} has no catalog"
    assert ds["catalog"]["tableDescription"]
    assert all(c["description"] and c["role"] for c in ds["catalog"]["columns"])


@step(r'the connection reports "AlbumId" as the primary key of "Album"')
def then_album_pk(ctx: ScenarioContext) -> None:
    body = httpx.get(f"{ctx.api}/api/databases").json()[0]
    album = next(t for t in body["tables"] if t["name"] == "Album")
    assert album["primaryKey"] == ["AlbumId"], album["primaryKey"]


@step(r'the connection reports that "Album" references "Artist"')
def then_album_fk(ctx: ScenarioContext) -> None:
    body = httpx.get(f"{ctx.api}/api/databases").json()[0]
    album = next(t for t in body["tables"] if t["name"] == "Album")
    refs = {fk["referencedTable"] for fk in album["foreignKeys"]}
    assert "Artist" in refs, refs


@step(r'the catalog describes "ArtistId" of "chinook\.Album" as a declared foreign key')
def then_catalog_marks_fk(ctx: ScenarioContext) -> None:
    ds = httpx.get(f"{ctx.api}/api/datasets/chinook.Album").json()
    artist_id = next(c for c in ds["catalog"]["columns"] if c["name"] == "ArtistId")
    assert "foreign key" in artist_id["description"].lower()
    assert "Artist" in artist_id["description"]


@step(r"no connection response or listing reveals the password")
def then_no_password_leak(ctx: ScenarioContext) -> None:
    secret = ctx.data["secret"]
    assert ctx.response is not None and ctx.response.status_code == 201
    payloads = [
        ctx.response.text,
        httpx.get(f"{ctx.api}/api/databases").text,
        httpx.get(f"{ctx.api}/api/datasets").text,
    ]
    for payload in payloads:
        assert secret not in payload, "secret leaked in a response"
        assert "password" not in json.dumps(json.loads(payload)).lower()


@step(r'the client detaches the connection "(?P<name>[^"]+)"')
def when_detach(ctx: ScenarioContext, name: str) -> None:
    ctx.response = httpx.delete(f"{ctx.api}/api/databases/{name}")


@step(r'the connection "(?P<name>[^"]+)" is no longer listed')
def then_connection_gone(ctx: ScenarioContext, name: str) -> None:
    names = {c["name"] for c in httpx.get(f"{ctx.api}/api/databases").json()}
    assert name not in names


@step(r'no "(?P<name>[^"]+)" tables remain among the datasets')
def then_no_connected_datasets(ctx: ScenarioContext, name: str) -> None:
    datasets = {d["name"] for d in httpx.get(f"{ctx.api}/api/datasets").json()}
    leftovers = {d for d in datasets if d.startswith(f"{name}.")}
    assert not leftovers, f"datasets left behind: {leftovers}"


@step(r"a client connects to an unreachable PostgreSQL server")
def when_connect_unreachable(ctx: ScenarioContext) -> None:
    ctx.response = httpx.post(
        f"{ctx.api}/api/databases/connect",
        json={
            "name": "pg",
            "engine": "postgres",
            "host": "127.0.0.1",
            "port": 1,
            "database": "pagila",
            "user": "u",
            "password": "p",
        },
        timeout=60.0,
    )


@step(r"the connection is rejected as a client error with a clear reason")
def then_rejected_clearly(ctx: ScenarioContext) -> None:
    assert ctx.response is not None
    assert 400 <= ctx.response.status_code < 500, (
        f"expected 4xx, got {ctx.response.status_code}"
    )
    assert ctx.response.json()["detail"]


@step(r"no server error occurs")
def then_no_server_error(ctx: ScenarioContext) -> None:
    assert ctx.response is not None and ctx.response.status_code < 500


@step(r"the second connection is rejected as already existing")
def then_duplicate_rejected(ctx: ScenarioContext) -> None:
    assert ctx.response is not None and ctx.response.status_code == 409
    assert "chinook" in ctx.response.json()["detail"]


@step(r'the detach is answered not-found, naming "(?P<name>[^"]+)"')
def then_detach_not_found(ctx: ScenarioContext, name: str) -> None:
    assert ctx.response is not None and ctx.response.status_code == 404
    assert name in ctx.response.json()["detail"]


# --------------------------------------------------------------------------- #
# Frontend-flow steps (AC-9..AC-11)
# --------------------------------------------------------------------------- #
@step(r"the analyst app is open in a browser")
def given_app_open(ctx: ScenarioContext) -> None:
    expect = _expect()
    ctx.page.goto(ctx.web)
    expect(ctx.page.get_by_text("Semantic catalog").first).to_be_visible()


@step(r"the user opens the database connection form")
def when_open_connect_form(ctx: ScenarioContext) -> None:
    ctx.page.get_by_role("button", name="Connect a database").click()
    _expect()(ctx.page.get_by_label("Connection name")).to_be_visible()


def _fill_sqlite_form(ctx: ScenarioContext, name: str) -> None:
    ctx.page.get_by_label("Connection name").fill(name)
    ctx.page.get_by_label("Database engine").select_option("sqlite")
    ctx.page.get_by_label("Database file path").fill(_db_path(ctx))
    ctx.page.get_by_role("button", name="Connect database").click()


@step(r'the user connects the sample database as "(?P<name>[^"]+)" through the form')
def when_connect_via_form(ctx: ScenarioContext, name: str) -> None:
    _fill_sqlite_form(ctx, name)


@step(
    r'the user has connected the sample database as "(?P<name>[^"]+)" through the form'
)
def given_connected_via_form(ctx: ScenarioContext, name: str) -> None:
    given_app_open(ctx)
    when_open_connect_form(ctx)
    _fill_sqlite_form(ctx, name)
    then_connection_visible(ctx, name)


@step(r'"(?P<name>[^"]+)" appears among the connected databases')
def then_connection_visible(ctx: ScenarioContext, name: str) -> None:
    _expect()(
        ctx.page.get_by_role("button", name=f"Detach database {name}")
    ).to_be_visible(timeout=20_000)


@step(r'the table "(?P<table>[^"]+)" appears in the semantic catalog')
def then_table_in_catalog(ctx: ScenarioContext, table: str) -> None:
    _expect()(ctx.page.get_by_text(table).first).to_be_visible()


@step(r'the user detaches the database "(?P<name>[^"]+)"')
def when_detach_via_ui(ctx: ScenarioContext, name: str) -> None:
    ctx.page.get_by_role("button", name=f"Detach database {name}").click()


@step(r'"(?P<name>[^"]+)" no longer appears among the connected databases')
def then_connection_gone_from_ui(ctx: ScenarioContext, name: str) -> None:
    _expect()(
        ctx.page.get_by_role("button", name=f"Detach database {name}")
    ).to_have_count(0)


@step(r'the table "(?P<table>[^"]+)" no longer appears in the semantic catalog')
def then_table_gone_from_catalog(ctx: ScenarioContext, table: str) -> None:
    _expect()(ctx.page.get_by_text(table)).to_have_count(0)


@step(r"the user submits an unreachable PostgreSQL connection")
def when_submit_unreachable_via_form(ctx: ScenarioContext) -> None:
    page = ctx.page
    page.get_by_label("Connection name").fill("pg")
    page.get_by_label("Database engine").select_option("postgres")
    page.get_by_label("Host").fill("127.0.0.1")
    page.get_by_label("Port").fill("1")
    page.get_by_label("Database name").fill("pagila")
    page.get_by_label("Username").fill("u")
    page.get_by_label("Password").fill("p")
    page.get_by_role("button", name="Connect database").click()


@step(r"the form shows that the connection failed with a reason")
def then_form_shows_failure(ctx: ScenarioContext) -> None:
    alert = ctx.page.get_by_role("alert")
    _expect()(alert).to_be_visible(timeout=20_000)
    assert "connect" in (alert.inner_text() or "").lower()
