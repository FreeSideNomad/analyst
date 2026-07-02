"""API-layer tests (feature 002) — AC-1..AC-5 via FastAPI TestClient.

Fixtures mode exercises the retained Python mock; store mode exercises the real
IngestionService/DuckDB path (no LLM — the service is built without a
cataloguer). The mock is opt-in: repository selection defaults to the store.
"""

import time

import pytest
from fastapi.testclient import TestClient

from analyst.api import repository as repo_mod
from analyst.api.app import create_app, fixtures_enabled
from analyst.api.repository import FixtureRepository, StoreRepository

CSV = "id,amount\n1,10\n2,20\n3,30\n"


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(FixtureRepository()))


# --------------------------------------------------------------------------- #
# AC-2 — repository selection: real store default, fixtures opt-in
# --------------------------------------------------------------------------- #
def test_fixtures_are_opt_in_not_default(monkeypatch, tmp_path):
    monkeypatch.delenv("ANALYST_FIXTURES", raising=False)
    assert fixtures_enabled() is False
    monkeypatch.setenv("ANALYST_FIXTURES", "1")
    assert fixtures_enabled() is True


def test_default_repository_is_the_real_store(monkeypatch, tmp_path):
    from analyst.api.app import _build_repository

    monkeypatch.delenv("ANALYST_FIXTURES", raising=False)
    monkeypatch.setenv("ANALYST_DATA_DIR", str(tmp_path / "data"))
    assert isinstance(_build_repository(), StoreRepository)
    monkeypatch.setenv("ANALYST_FIXTURES", "1")
    assert isinstance(_build_repository(), FixtureRepository)


def test_health_reports_mode(monkeypatch):
    monkeypatch.setenv("ANALYST_FIXTURES", "1")
    body = TestClient(create_app(FixtureRepository())).get("/api/health").json()
    assert body["ok"] is True and body["fixtures"] is True


# --------------------------------------------------------------------------- #
# AC-1 — datasets served in domain-true wire shapes (fixtures mode)
# --------------------------------------------------------------------------- #
def test_list_datasets_wire_shape(client):
    datasets = client.get("/api/datasets").json()
    assert {d["name"] for d in datasets} == {"sales", "customers", "products"}
    sales = next(d for d in datasets if d["name"] == "sales")
    # envelope
    assert sales["id"] == "sales" and sales["fileName"] == "sales.csv"
    assert sales["status"] == "complete"
    assert sales["rowCount"] == sales["profile"]["rowCount"]
    assert sales["columnCount"] == len(sales["profile"]["columns"])
    # profile columns carry the domain facts, camelCased
    col = sales["profile"]["columns"][0]
    assert {"inferredType", "nullRate", "distinctCount", "samples"} <= set(col)
    # catalog mirrors CatalogEntry
    assert sales["catalog"]["tableDescription"]
    assert all(
        {"name", "description", "role"} <= set(c) for c in sales["catalog"]["columns"]
    )


def test_get_dataset_and_catalog(client):
    one = client.get("/api/datasets/sales")
    assert one.status_code == 200 and one.json()["name"] == "sales"
    catalog = client.get("/api/catalog").json()
    assert "sales" in catalog and catalog["sales"]["tableDescription"]


# --------------------------------------------------------------------------- #
# AC-4 — unknown datasets 404
# --------------------------------------------------------------------------- #
def test_unknown_dataset_404s(client):
    for call in (
        lambda: client.get("/api/datasets/nope"),
        lambda: client.delete("/api/datasets/nope"),
        lambda: client.post(
            "/api/datasets/nope/refresh", files={"file": ("x.csv", CSV.encode())}
        ),
    ):
        response = call()
        assert response.status_code == 404
        assert "nope" in response.json()["detail"]


# --------------------------------------------------------------------------- #
# AC-3 — ingest / status / refresh / delete lifecycle (fixtures mode)
# --------------------------------------------------------------------------- #
def test_ingest_status_lifecycle(client, monkeypatch):
    monkeypatch.setattr(repo_mod, "_SIM_SECONDS", 0.05)
    result = client.post(
        "/api/datasets/ingest", files={"file": ("transactions_q4.csv", CSV.encode())}
    ).json()
    name = result["datasets"][0]["name"]
    assert result["datasets"][0]["status"] == "in progress"
    time.sleep(0.06)
    status = client.get(f"/api/ingestion/{name}/status").json()
    assert status["status"] == "complete" and status["progress"] == 100


def test_refresh_and_delete(client):
    refreshed = client.post(
        "/api/datasets/sales/refresh", files={"file": ("sales.csv", CSV.encode())}
    ).json()
    assert refreshed["replaced"] is True and refreshed["version"] == 2
    assert client.delete("/api/datasets/sales").status_code == 204
    assert client.get("/api/datasets/sales").status_code == 404
    assert "sales" not in {d["name"] for d in client.get("/api/datasets").json()}


# --------------------------------------------------------------------------- #
# AC-5 — provisional Q&A: clarify-then-answer with a trust trail
# --------------------------------------------------------------------------- #
def test_qa_clarify_then_answer(client):
    clarification = client.post(
        "/api/query", json={"question": "What is the revenue by region?"}
    ).json()
    assert clarification["type"] == "clarification"
    assert len(clarification["options"]) >= 2
    answer = client.post(
        f"/api/query/{clarification['queryId']}/respond",
        json={"selectedOptions": [clarification["options"][0]]},
    ).json()
    assert answer["type"] == "answer" and answer["summary"]
    trail = answer["trustTrail"]
    assert trail["assumptions"] and trail["lineage"] and trail["sql"]


def test_qa_unambiguous_answers_directly(client):
    answer = client.post(
        "/api/query", json={"question": "What is the average order value?"}
    ).json()
    assert answer["type"] == "answer"


# --------------------------------------------------------------------------- #
# Store mode — the real engine behind the same endpoints (no LLM)
# --------------------------------------------------------------------------- #
@pytest.fixture
def store_client(tmp_path) -> TestClient:
    return TestClient(create_app(StoreRepository(str(tmp_path / "data"))))


def test_store_mode_real_ingest_and_query(store_client):
    result = store_client.post(
        "/api/datasets/ingest", files={"file": ("numbers.csv", CSV.encode())}
    ).json()
    ds = result["datasets"][0]
    assert ds["name"] == "numbers" and ds["status"] == "complete"
    assert ds["rowCount"] == 3
    types = {c["name"]: c["inferredType"] for c in ds["profile"]["columns"]}
    assert types == {"id": "integer", "amount": "integer"}


def test_store_mode_refresh_versions_and_delete(store_client):
    store_client.post(
        "/api/datasets/ingest", files={"file": ("numbers.csv", CSV.encode())}
    )
    conforming = "id,amount\n5,50\n6,60\n"
    refreshed = store_client.post(
        "/api/datasets/numbers/refresh",
        files={"file": ("numbers.csv", conforming.encode())},
    ).json()
    assert refreshed["replaced"] is True and refreshed["version"] == 2
    assert store_client.get("/api/datasets/numbers").json()["rowCount"] == 2
    assert store_client.delete("/api/datasets/numbers").status_code == 204
    assert store_client.get("/api/datasets/numbers").status_code == 404
