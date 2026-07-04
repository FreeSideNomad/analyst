"""API tests (feature 005) — /api/databases connect/list/detach.

FastAPI TestClient over fixtures mode; the sample DB is the bundled Chinook
SQLite fixture (real federation, deterministic, offline).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from analyst.api.app import create_app
from analyst.api.repository import FixtureRepository

CHINOOK = Path(__file__).resolve().parent.parent / "golden" / "chinook.sqlite"


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(FixtureRepository()))


@pytest.fixture
def db_path(tmp_path) -> Path:
    target = tmp_path / "chinook.sqlite"
    shutil.copy(CHINOOK, target)
    return target


def _connect(client, db_path, name="chinook", **extra):
    payload = {"name": name, "engine": "sqlite", "path": str(db_path), **extra}
    return client.post("/api/databases/connect", json=payload)


# --------------------------------------------------------------------------- #
# AC-1 / AC-2 — connect exposes profiled, catalogued datasets
# --------------------------------------------------------------------------- #
def test_connect_registers_tables_as_datasets(client, db_path):
    response = _connect(client, db_path)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "chinook" and body["engine"] == "sqlite"
    assert {t["name"] for t in body["tables"]} >= {"Album", "Artist", "Track"}

    names = {d["name"] for d in client.get("/api/datasets").json()}
    assert {"chinook.Album", "chinook.Artist", "chinook.Track"} <= names


def test_connected_dataset_is_profiled_and_catalogued(client, db_path):
    _connect(client, db_path)
    ds = client.get("/api/datasets/chinook.Album").json()
    assert ds["rowCount"] == 53
    assert {c["name"] for c in ds["profile"]["columns"]} == {
        "AlbumId",
        "Title",
        "ArtistId",
    }
    assert ds["catalog"]["tableDescription"]
    roles = {c["name"]: c["role"] for c in ds["catalog"]["columns"]}
    assert roles["AlbumId"] == "identifier"


# --------------------------------------------------------------------------- #
# AC-3 — declared keys on the wire
# --------------------------------------------------------------------------- #
def test_declared_keys_are_reported(client, db_path):
    body = _connect(client, db_path).json()
    album = next(t for t in body["tables"] if t["name"] == "Album")
    assert album["primaryKey"] == ["AlbumId"]
    fk = album["foreignKeys"][0]
    assert fk["referencedTable"] == "Artist" and fk["columns"] == ["ArtistId"]


# --------------------------------------------------------------------------- #
# AC-4 — secrets never returned
# --------------------------------------------------------------------------- #
def test_no_response_ever_contains_the_password(client, db_path):
    secret = "s3cret-hunter2"
    connect_body = _connect(client, db_path, password=secret).text
    listing = client.get("/api/databases").text
    datasets = client.get("/api/datasets").text
    for payload in (connect_body, listing, datasets):
        assert secret not in payload
        assert "password" not in json.dumps(json.loads(payload)).lower()


# --------------------------------------------------------------------------- #
# AC-5 — list + detach
# --------------------------------------------------------------------------- #
def test_list_and_detach_removes_datasets(client, db_path):
    _connect(client, db_path)
    listed = client.get("/api/databases").json()
    assert [c["name"] for c in listed] == ["chinook"]

    assert client.delete("/api/databases/chinook").status_code == 204
    assert client.get("/api/databases").json() == []
    names = {d["name"] for d in client.get("/api/datasets").json()}
    assert not any(n.startswith("chinook.") for n in names)
    # seeded fixture datasets untouched
    assert {"sales", "customers", "products"} <= names


# --------------------------------------------------------------------------- #
# AC-6/7/8 — clean failures
# --------------------------------------------------------------------------- #
def test_unreachable_postgres_is_a_clean_client_error(client):
    response = client.post(
        "/api/databases/connect",
        json={
            "name": "pg",
            "engine": "postgres",
            "host": "127.0.0.1",
            "port": 1,
            "database": "pagila",
            "user": "u",
            "password": "p",
        },
    )
    assert 400 <= response.status_code < 500
    assert response.json()["detail"]


def test_duplicate_name_is_a_conflict(client, db_path):
    _connect(client, db_path)
    response = _connect(client, db_path)
    assert response.status_code == 409
    assert "chinook" in response.json()["detail"]


def test_detach_unknown_is_not_found(client):
    response = client.delete("/api/databases/nope")
    assert response.status_code == 404
    assert "nope" in response.json()["detail"]


def test_invalid_spec_is_a_client_error(client):
    response = client.post(
        "/api/databases/connect", json={"name": "x", "engine": "sqlite"}
    )
    assert response.status_code in (400, 422)


# --------------------------------------------------------------------------- #
# Reset seam — /api/_reset also resets connections (e2e isolation)
# --------------------------------------------------------------------------- #
def test_reset_clears_connections(client, db_path, monkeypatch):
    monkeypatch.setenv("ANALYST_FIXTURES", "1")
    _connect(client, db_path)
    assert client.get("/api/databases").json()
    client.post("/api/_reset")
    assert client.get("/api/databases").json() == []
    names = {d["name"] for d in client.get("/api/datasets").json()}
    assert not any(n.startswith("chinook.") for n in names)
