"""Feature 016 — catalog curation: prompt/schema, repository lifecycle,
stickiness, offline fallback, blast radius."""

from __future__ import annotations

import dataclasses

import pytest

from analyst.agentic.curation import (
    CurationError,
    CurationResult,
    Curator,
    render_curation_prompt,
)
from analyst.api.repository import StoreRepository
from analyst.domain.catalog import (
    CatalogEntry,
    Clarification,
    ColumnDescription,
    UnknownCurationError,
    payload_from_profile,
)

ORDERS = "order_id,status,amount\nO1,fulfilled,10\nO2,unfulfilled,20\nO3,fulfilled,30\nO4,unfulfilled,40\nO5,fulfilled,50\nO6,fulfilled,60\n"

CLARIFICATION = Clarification(
    question="What does the 'status' column describe?",
    options=(
        "Account/subscription state of the customer",
        "Fulfillment state of a sale or order",
        "Payment state (paid/pending/failed)",
    ),
    column="status",
)


class StubCurator:
    """Deterministic curator standing in for the gateway-backed one."""

    def __init__(self, column_description=None, table_description=None, fail=False):
        self.column_description = column_description
        self.table_description = table_description
        self.fail = fail
        self.calls: list[dict] = []

    def complete(self, payload, column, question, user_input, **kwargs):
        self.calls.append({"column": column, "question": question, "input": user_input})
        if self.fail:
            raise CurationError("synthesis failed")
        return CurationResult(
            column_description=self.column_description,
            table_description=self.table_description,
        )


def _repo(tmp_path, curator=None) -> StoreRepository:
    return StoreRepository(str(tmp_path / "data"), curator=curator)


def _seed(repo, name="orders.csv", text=ORDERS) -> str:
    (rec,) = repo.ingest(name, text.encode())
    entry = rec.summary.catalog or CatalogEntry(
        table_description="Orders with a status and an amount.",
        columns=tuple(
            ColumnDescription(c.name, f"Column {c.name}.", "category")
            for c in rec.summary.profile.columns
        ),
    )
    entry = dataclasses.replace(entry, clarifications=(CLARIFICATION,))
    repo.attach_catalog(rec.name, entry)
    return rec.name


# --------------------------------------------------------------------------- #
# Agentic module
# --------------------------------------------------------------------------- #
def test_prompt_carries_evidence_and_answer_but_never_rows(tmp_path):
    repo = _repo(tmp_path)
    name = _seed(repo)
    payload = payload_from_profile(name, repo.get_dataset(name).summary.profile)
    prompt = render_curation_prompt(
        payload,
        "status",
        CLARIFICATION.question,
        "Fulfillment state of a sale or order",
        "Column status.",
        "Orders with a status and an amount.",
    )
    assert "ground truth" in prompt.lower()
    assert "Fulfillment state of a sale or order" in prompt
    assert CLARIFICATION.question in prompt
    assert "O3" not in prompt  # sample values are capped metadata, not rows


def test_curator_parse_failure_is_a_curation_error():
    class BadBackend:
        def complete(self, request):
            return "not json at all"

    from analyst.agentic.gateway import LLMGateway

    curator = Curator(LLMGateway(BadBackend()))
    with pytest.raises(CurationError):
        curator.complete(payload_from_profile("t", _EMPTY_PROFILE), "c", None, "answer")


from analyst.domain.profile import DatasetProfile  # noqa: E402

_EMPTY_PROFILE = DatasetProfile(row_count=0)


# --------------------------------------------------------------------------- #
# Repository: answering
# --------------------------------------------------------------------------- #
def test_answer_updates_description_and_clears_clarification(tmp_path):
    curator = StubCurator(
        column_description="Fulfillment state of the order (fulfilled/unfulfilled).",
        table_description="Customer orders with their fulfillment state and amount.",
    )
    repo = _repo(tmp_path, curator=curator)
    name = _seed(repo)
    repo.answer_clarification(name, "status", "Fulfillment state of a sale or order")
    entry = repo.get_dataset(name).summary.catalog
    status = next(c for c in entry.columns if c.name == "status")
    assert "Fulfillment state" in status.description
    assert "fulfillment state" in entry.table_description.lower()
    assert entry.clarifications == ()
    assert curator.calls[0]["question"] == CLARIFICATION.question


def test_blast_radius_only_column_and_own_table(tmp_path):
    curator = StubCurator(
        column_description="New meaning.", table_description="New table meaning."
    )
    repo = _repo(tmp_path, curator=curator)
    name = _seed(repo)
    other = _seed_second(repo)
    before = repo.get_dataset(other).summary.catalog
    before_own = {
        c.name: c.description
        for c in repo.get_dataset(name).summary.catalog.columns
        if c.name != "status"
    }
    repo.answer_clarification(name, "status", "Fulfillment state of a sale or order")
    assert repo.get_dataset(other).summary.catalog == before
    entry = repo.get_dataset(name).summary.catalog
    after_own = {c.name: c.description for c in entry.columns if c.name != "status"}
    assert after_own == before_own


def _seed_second(repo) -> str:
    (rec,) = repo.ingest("customers.csv", b"customer_id,region\nC1,East\nC2,West\n")
    entry = CatalogEntry(
        table_description="Customer master data.",
        columns=(
            ColumnDescription("customer_id", "Column customer_id.", "identifier"),
            ColumnDescription("region", "Column region.", "category"),
        ),
    )
    repo.attach_catalog(rec.name, entry)
    return rec.name


def test_provenance_and_badge(tmp_path):
    repo = _repo(tmp_path, curator=StubCurator(column_description="Settled."))
    name = _seed(repo)
    repo.answer_clarification(name, "status", "Fulfillment state of a sale or order")
    state = repo.curation(name)
    assert state["columns"]["status"]["kind"] == "answer"
    assert state["columns"]["status"]["input"] == "Fulfillment state of a sale or order"


def test_sticky_across_recatalogue_and_restart(tmp_path):
    repo = _repo(tmp_path, curator=StubCurator(column_description="Settled meaning."))
    name = _seed(repo)
    repo.answer_clarification(name, "status", "Fulfillment state of a sale or order")
    # simulate an automatic re-derivation clobbering the entry
    fresh = CatalogEntry(
        table_description="Rederived table text.",
        columns=(ColumnDescription("status", "Rederived description.", "category"),),
        clarifications=(CLARIFICATION,),
    )
    repo.attach_catalog(name, fresh)  # attach applies the curation overlay
    entry = repo.get_dataset(name).summary.catalog
    status = next(c for c in entry.columns if c.name == "status")
    assert status.description == "Settled meaning."
    assert entry.clarifications == ()  # answered question never re-opens
    # restart
    reborn = _repo(tmp_path)
    entry = reborn.get_dataset(name).summary.catalog
    status = next(c for c in entry.columns if c.name == "status")
    assert status.description == "Settled meaning."
    assert reborn.curation(name)["columns"]["status"]["kind"] == "answer"


def test_failed_synthesis_changes_nothing(tmp_path):
    repo = _repo(tmp_path, curator=StubCurator(fail=True))
    name = _seed(repo)
    before = repo.get_dataset(name).summary.catalog
    with pytest.raises(CurationError):
        repo.answer_clarification(
            name, "status", "Fulfillment state of a sale or order"
        )
    assert repo.get_dataset(name).summary.catalog == before
    assert repo.curation(name)["columns"] == {}


def test_empty_and_unknown_are_clean(tmp_path):
    repo = _repo(tmp_path, curator=StubCurator(column_description="x"))
    name = _seed(repo)
    with pytest.raises(ValueError):
        repo.answer_clarification(name, "status", "   ")
    with pytest.raises(UnknownCurationError):
        repo.answer_clarification(name, "no_such_column", "whatever")


# --------------------------------------------------------------------------- #
# Corrections + offline fallback
# --------------------------------------------------------------------------- #
def test_correction_on_column_and_table(tmp_path):
    curator = StubCurator(column_description="The settlement date of the transaction.")
    repo = _repo(tmp_path, curator=curator)
    name = _seed(repo)
    repo.suggest_correction(name, "order_id", "Actually the settlement reference")
    entry = repo.get_dataset(name).summary.catalog
    col = next(c for c in entry.columns if c.name == "order_id")
    assert col.description == "The settlement date of the transaction."
    curator.table_description = "Wholesale transactions only."
    curator.column_description = None
    repo.suggest_correction(name, None, "These are wholesale transactions only")
    assert (
        repo.get_dataset(name).summary.catalog.table_description
        == "Wholesale transactions only."
    )


def test_offline_answer_and_correction_are_verbatim_and_pending(tmp_path):
    repo = _repo(tmp_path, curator=None)
    name = _seed(repo)
    repo.answer_clarification(name, "status", "Fulfillment state of a sale or order")
    entry = repo.get_dataset(name).summary.catalog
    status = next(c for c in entry.columns if c.name == "status")
    assert "Fulfillment state of a sale or order" in status.description
    assert entry.clarifications == ()
    state = repo.curation(name)
    assert state["columns"]["status"]["pending_reconciliation"] is True

    repo.suggest_correction(name, "order_id", "The settlement reference")
    col = next(
        c
        for c in repo.get_dataset(name).summary.catalog.columns
        if c.name == "order_id"
    )
    assert col.description == "The settlement reference"


# --------------------------------------------------------------------------- #
# API routes
# --------------------------------------------------------------------------- #
from fastapi.testclient import TestClient  # noqa: E402

from analyst.api.app import create_app  # noqa: E402
from analyst.api.repository import FixtureRepository  # noqa: E402


def test_curation_routes_answer_and_correct(tmp_path):
    curator = StubCurator(
        column_description="Fulfillment state of the order.",
        table_description="Orders and their fulfillment state.",
    )
    repo = _repo(tmp_path, curator=curator)
    name = _seed(repo)
    client = TestClient(create_app(repo))

    state = client.get(f"/api/datasets/{name}/curation").json()
    assert state["columns"] == {} and state["clarifications"][0]["column"] == "status"

    body = client.post(
        f"/api/datasets/{name}/curation/answer",
        json={"column": "status", "answer": "Fulfillment state of a sale or order"},
    ).json()
    assert body["columns"]["status"]["kind"] == "answer"
    assert body["clarifications"] == []

    body = client.post(
        f"/api/datasets/{name}/curation/correct",
        json={"note": "Wholesale transactions only"},
    ).json()
    assert body["table"]["kind"] == "correction"


def test_curation_route_errors(tmp_path):
    repo = _repo(tmp_path, curator=StubCurator(fail=True))
    name = _seed(repo)
    client = TestClient(create_app(repo))
    r = client.post(
        f"/api/datasets/{name}/curation/answer",
        json={"column": "status", "answer": "  "},
    )
    assert r.status_code == 400
    r = client.post(
        f"/api/datasets/{name}/curation/answer",
        json={"column": "ghost", "answer": "x"},
    )
    assert r.status_code == 404
    r = client.post(
        f"/api/datasets/{name}/curation/answer",
        json={"column": "status", "answer": "Fulfillment state of a sale or order"},
    )
    assert r.status_code == 502
    assert client.get("/api/datasets/nope/curation").status_code == 404


def test_fixture_repo_supports_curation_flow():
    client = TestClient(create_app(FixtureRepository()))
    state = client.get("/api/datasets/sales/curation").json()
    assert state["clarifications"][0]["column"] == "channel"
    body = client.post(
        "/api/datasets/sales/curation/answer",
        json={
            "column": "channel",
            "answer": "Sales channel the order was placed through",
        },
    ).json()
    assert body["clarifications"] == []
    assert body["columns"]["channel"]["kind"] == "answer"
    body = client.post(
        "/api/datasets/sales/curation/correct",
        json={"column": "billing_region", "note": "Region of the billing address"},
    ).json()
    assert body["columns"]["billing_region"]["kind"] == "correction"
