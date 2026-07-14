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
    assert ds["name"] == "numbers.csv" and ds["status"] == "complete"
    assert ds["group"] == "numbers.csv" and ds["entity"] == "numbers"
    assert ds["sourceKind"] == "file" and ds["queryable"]
    assert ds["rowCount"] == 3
    types = {c["name"]: c["inferredType"] for c in ds["profile"]["columns"]}
    assert types == {"id": "integer", "amount": "integer"}


def test_store_mode_refresh_versions_and_delete(store_client):
    store_client.post(
        "/api/datasets/ingest", files={"file": ("numbers.csv", CSV.encode())}
    )
    conforming = "id,amount\n5,50\n6,60\n"
    refreshed = store_client.post(
        "/api/datasets/numbers.csv/refresh",
        files={"file": ("numbers.csv", conforming.encode())},
    ).json()
    assert refreshed["replaced"] is True and refreshed["version"] == 2
    assert store_client.get("/api/datasets/numbers.csv").json()["rowCount"] == 2
    assert store_client.delete("/api/datasets/numbers.csv").status_code == 204
    assert store_client.get("/api/datasets/numbers.csv").status_code == 404


# --------------------------------------------------------------------------- #
# Defect regression (exploratory 2026-07-02): domain validation errors must
# surface as clean 4xx with the domain's friendly message — never 500s.
# --------------------------------------------------------------------------- #
def test_empty_file_is_rejected_with_400(store_client):
    response = store_client.post(
        "/api/datasets/ingest", files={"file": ("empty.csv", b"")}
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_unsupported_format_is_rejected_with_400(store_client):
    response = store_client.post(
        "/api/datasets/ingest", files={"file": ("report.pdf", b"%PDF-1.4 nope")}
    )
    assert response.status_code == 400
    assert "CSV" in response.json()["detail"]


def test_oversize_file_is_rejected_with_413(tmp_path):
    repo = StoreRepository(str(tmp_path / "data"))
    repo.service.max_bytes = 10
    response = TestClient(create_app(repo)).post(
        "/api/datasets/ingest", files={"file": ("big.csv", CSV.encode())}
    )
    assert response.status_code == 413
    assert "too large" in response.json()["detail"].lower()


def test_fixture_mode_also_rejects_empty_files(client):
    response = client.post("/api/datasets/ingest", files={"file": ("empty.csv", b"")})
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


class _AsyncioRunCataloguer:
    """Mirrors the live backend's contract: catalog() drives its own event
    loop via asyncio.run() (claude_backend.complete does exactly this), so it
    MUST run off the server's event-loop thread or it raises RuntimeError."""

    def catalog(self, payload, relationships=(), context=None):
        import asyncio

        from analyst.domain.catalog import CatalogEntry

        async def _describe() -> str:
            return "Customer orders with revenue by region and channel."

        return CatalogEntry(table_description=asyncio.run(_describe()), columns=())


def test_live_style_cataloguer_works_through_the_ingest_route(tmp_path):
    """Regression (2026-07-14): the async ingest route ran repo.ingest() on
    the event-loop thread, so every LIVE-catalogued upload died with
    'asyncio.run() cannot be called from a running event loop' -> 500."""
    repo = StoreRepository(str(tmp_path / "data"), cataloguer=_AsyncioRunCataloguer())
    response = TestClient(create_app(repo)).post(
        "/api/datasets/ingest", files={"file": ("orders.csv", CSV.encode())}
    )
    assert response.status_code == 200
    (record,) = response.json()["datasets"]
    assert record["catalog"]["tableDescription"].startswith("Customer orders")


# --------------------------------------------------------------------------- #
# Security hardening (review 2026-07-04). Each test reproduces a CONFIRMED
# exploit found by the independent adversarial review, then locks the fix.
# --------------------------------------------------------------------------- #
def test_C1_upload_filename_traversal_is_contained(tmp_path):
    """CRITICAL C1: a `../`-laden upload filename must not escape the temp dir."""
    import tempfile
    from pathlib import Path

    repo = StoreRepository(str(tmp_path / "data"))
    marker = f"ESCAPED_{abs(hash(tmp_path))}.csv"
    # The reviewer's exploit: a single `../` escaped the internal TemporaryDirectory
    # into the system temp root. Reproduce and assert containment.
    repo.ingest(f"../{marker}", b"id,amount\n1,10\n2,20\n")
    escaped = Path(tempfile.gettempdir()) / marker
    assert not escaped.exists(), f"upload filename escaped to {escaped}"


def test_C1_safe_upload_name_strips_path():
    from analyst.api.repository import _safe_upload_name

    assert _safe_upload_name("../../etc/passwd") == "passwd"
    assert _safe_upload_name("/abs/path/x.csv") == "x.csv"
    assert _safe_upload_name("..\\..\\windows\\evil.csv").endswith("evil.csv")
    assert _safe_upload_name("") == "upload.csv"
    assert _safe_upload_name("   ") == "upload.csv"
    assert _safe_upload_name("normal.csv") == "normal.csv"


def test_H2_datasets_survive_a_restart_at_the_api_level(tmp_path):
    """HIGH H2: a new StoreRepository on the same data dir must still list and
    serve datasets ingested before (the DuckDB catalog + parquet persist)."""
    data = str(tmp_path / "data")
    StoreRepository(data).ingest("survivors.csv", CSV.encode())
    # simulate a process restart: brand-new repository, same directory
    reopened = StoreRepository(data)
    names = {r.name for r in reopened.list_datasets()}
    assert "survivors.csv" in names, "dataset vanished from the API after restart"
    assert reopened.get_dataset("survivors.csv").summary.profile.row_count == 3


def test_H4_malformed_json_is_rejected_as_400_not_500(store_client):
    """HIGH H4: a malformed JSON upload must surface as a clean 4xx, not a 500."""
    resp = store_client.post(
        "/api/datasets/ingest",
        files={"file": ("bad.json", b"{ this is : not json ]")},
    )
    assert resp.status_code == 400, f"got {resp.status_code}: {resp.text[:120]}"


def test_M3_real_ingest_gets_a_catalog_and_it_persists(tmp_path, monkeypatch):
    """M3/gap#3: with a cataloguer wired, a real upload gets descriptions/roles,
    surfaces via /api/catalog, and survives a restart (replayed — CI-safe)."""
    from analyst.api.app import build_cataloguer

    monkeypatch.setenv(
        "ANALYST_CATALOG_CASSETTE", "tests/cassettes/catalog_orders.json"
    )
    data = str(tmp_path / "data")
    csv = b"order_id,customer,amount_usd\n1,Acme,120.50\n2,Globex,89.00\n"
    repo = StoreRepository(data, cataloguer=build_cataloguer())
    recs = repo.ingest("orders.csv", csv)
    cat = recs[0].summary.catalog
    assert cat is not None and cat.table_description
    assert {c.name for c in cat.columns} == {"order_id", "customer", "amount_usd"}
    # persists across a restart via the sidecar (no cataloguer needed to reload)
    assert StoreRepository(data).get_dataset("orders.csv").summary.catalog is not None


def test_H3_oversize_upload_is_rejected_before_full_buffering(tmp_path, monkeypatch):
    """HIGH H3: an upload beyond the cap is rejected (413) via a bounded read."""
    monkeypatch.setenv("ANALYST_MAX_UPLOAD_BYTES", "1024")
    client = TestClient(create_app(StoreRepository(str(tmp_path / "data"))))
    big = b"id,v\n" + b"1,2\n" * 2000  # > 1 KiB
    resp = client.post("/api/datasets/ingest", files={"file": ("big.csv", big)})
    assert resp.status_code == 413
    assert "limit" in resp.json()["detail"].lower()


def test_group_and_entity_split():
    from analyst.api.routes.datasets import _group_and_entity

    assert _group_and_entity("company.employees.xlsx", False) == (
        "company.xlsx",
        "employees",
    )
    assert _group_and_entity("orders.csv", False) == ("orders.csv", "orders")
    assert _group_and_entity("sales_db.orders", True) == ("sales_db", "orders")


def test_corrupt_catalog_sidecar_does_not_brick_the_workspace(tmp_path):
    """Review #3 (HIGH): a corrupt/schema-drifted sidecar must not abort boot —
    that dataset just loses its cached catalog; healthy datasets survive."""
    from pathlib import Path

    from analyst.api.repository import StoreRepository

    data = str(tmp_path / "data")
    repo = StoreRepository(data)
    repo.ingest("good1.csv", b"id,amount\n1,10\n")
    repo.ingest("good2.csv", b"id,amount\n1,20\n")
    (Path(data) / "good1.csv.catalog.json").write_text("{corrupt json")

    reopened = StoreRepository(data)  # simulate a restart — must not raise
    names = {r.name for r in reopened.list_datasets()}
    assert {"good1.csv", "good2.csv"} <= names  # both survive


def test_files_get_semantic_analysis_by_default(tmp_path):
    """Parity with DB import: an ingested file gets a data-grounded semantic
    catalog (descriptions + roles) with NO LLM / env flag — not profile-only."""
    from analyst.api.repository import StoreRepository

    repo = StoreRepository(str(tmp_path / "data"))
    rec = repo.ingest("address.csv", b"address_id,district\n1,California\n2,Texas\n")[0]
    cat = rec.summary.catalog
    assert cat is not None
    assert cat.table_description
    district = next(c for c in cat.columns if c.name == "district")
    assert (
        district.description
        and district.description != "Text column from the source table."
    )
    assert district.role  # a role was inferred


# --------------------------------------------------------------------------- #
# Feature 010 — the repository supplies the workspace catalogs for cataloguing
# --------------------------------------------------------------------------- #
_CUSTOMERS_010 = b"id,region\n10,North\n20,South\n"
_ORDERS_010 = b"order_id,customer_id,quantity\n1,10,2\n2,20,1\n3,10,3\n"


def test_repository_ingest_catalogues_in_workspace_context(tmp_path):
    repo = StoreRepository(str(tmp_path / "data"))
    repo.ingest("customers.csv", _CUSTOMERS_010)
    (orders,) = repo.ingest("orders.csv", _ORDERS_010)
    fk = next(c for c in orders.summary.catalog.columns if c.name == "customer_id")
    # The sibling's meaning — not just its name — is woven in (AC-1/AC-2).
    assert "customers.csv: 2 rows, 2 columns" in fk.description


def test_workspace_context_survives_a_restart(tmp_path):
    """AC-11: a fresh session rebuilds the context from persisted catalogs."""
    data = str(tmp_path / "data")
    StoreRepository(data).ingest("customers.csv", _CUSTOMERS_010)
    reopened = StoreRepository(data)  # fresh session — catalogs from sidecars
    (orders,) = reopened.ingest("orders.csv", _ORDERS_010)
    fk = next(c for c in orders.summary.catalog.columns if c.name == "customer_id")
    assert "customers.csv: 2 rows, 2 columns" in fk.description


def test_new_relationship_recatalogues_the_affected_existing_table(tmp_path):
    """AC-4: an existing table learns it is now referenced by the new one."""
    repo = StoreRepository(str(tmp_path / "data"))
    repo.ingest("customers.csv", _CUSTOMERS_010)
    before = repo.get_dataset("customers.csv").summary.catalog.table_description
    assert "orders" not in before
    repo.ingest("orders.csv", _ORDERS_010)
    after = repo.get_dataset("customers.csv").summary.catalog
    assert "Referenced by orders.csv" in after.table_description
    # …and the refreshed meaning is persisted for the next session.
    reopened = StoreRepository(str(tmp_path / "data"))
    persisted = reopened.get_dataset("customers.csv").summary.catalog
    assert "Referenced by orders.csv" in persisted.table_description


def test_recataloguing_is_bounded_to_the_affected_tables(tmp_path):
    """AC-5: an unrelated table's entry is not re-derived (same object)."""
    repo = StoreRepository(str(tmp_path / "data"))
    repo.ingest("customers.csv", _CUSTOMERS_010)
    repo.ingest("products.csv", b"sku,label\nA1,Widget\nB2,Gadget\n")
    products_before = repo.get_dataset("products.csv").summary.catalog
    repo.ingest("orders.csv", _ORDERS_010)
    assert repo.get_dataset("products.csv").summary.catalog is products_before


def test_recataloguing_failure_keeps_the_prior_entry(tmp_path):
    """AC-10: a re-derivation failure is contained — ingest still succeeds."""
    repo = StoreRepository(str(tmp_path / "data"))
    repo.ingest("customers.csv", _CUSTOMERS_010)
    prior = repo.get_dataset("customers.csv").summary.catalog

    def boom(*args, **kwargs):
        raise RuntimeError("re-derivation failed")

    repo._derive_entry = boom
    (orders,) = repo.ingest("orders.csv", _ORDERS_010)  # must not raise
    assert orders.summary.catalog is not None
    assert repo.get_dataset("customers.csv").summary.catalog is prior


# --------------------------------------------------------------------------- #
# Distribution — the API serves the built frontend (single-image deploy)
# --------------------------------------------------------------------------- #
def test_serves_built_frontend_when_dist_configured(tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>analyst</title>")
    (dist / "app.js").write_text("console.log('ok')")
    monkeypatch.setenv("ANALYST_WEB_DIST", str(dist))
    monkeypatch.setenv("ANALYST_FIXTURES", "1")
    client = TestClient(create_app(FixtureRepository()))
    assert "analyst" in client.get("/").text
    assert client.get("/app.js").status_code == 200
    assert client.get("/api/health").status_code == 200  # API keeps priority


def test_no_dist_configured_keeps_api_only(monkeypatch):
    monkeypatch.delenv("ANALYST_WEB_DIST", raising=False)
    monkeypatch.setenv("ANALYST_FIXTURES", "1")
    client = TestClient(create_app(FixtureRepository()))
    assert client.get("/api/health").status_code == 200
