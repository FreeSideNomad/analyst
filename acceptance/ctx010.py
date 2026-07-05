"""Step handlers for feature 010 — workspace-aware cataloguing.

All scenarios bind over the in-process seam: a real ``StoreRepository`` (the
production wiring: DatasetStore + IngestionService + catalog_source) in the
pytest tmp_path, plus a ``DatabaseManager`` with a synthetic SQLite database
where a connected database is needed. No browser, no live model calls — the
LLM-path scenario replays a recorded cassette; the offline path is
deterministic by construction.

Given steps record fixture intent; the When step realizes the workspace with
the right cataloguer flavor (spy / offline / language-model / broken-context),
so one scenario never needs two repositories open at once. The spy cataloguer
records the exact ``WorkspaceContext`` each table's cataloguing received while
producing byte-identical output to the offline path.

Binding status: slice 1 bound (context cataloguing). Retroactive (slice 2)
and DB persistence (slice 3) steps intentionally fail NOT YET IMPLEMENTED.
"""

from __future__ import annotations

import dataclasses
import sqlite3
from pathlib import Path
from typing import Any

from acceptance.e2e_base import ScenarioContext, make_registry

step, run_step = make_registry()

__all__ = ["ScenarioContext", "run_step"]

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTEXT_CASSETTE = REPO_ROOT / "tests" / "cassettes" / "catalog_context.json"

CUSTOMERS_CSV = "id,region\n10,North\n20,South\n"
PRODUCTS_CSV = "sku,label\nA1,Widget\nB2,Gadget\n"
ORDERS_CSV = "order_id,customer_id,quantity\n1,10,2\n2,20,1\n3,10,3\n"


# --------------------------------------------------------------------------- #
# Scenario state + the realization machinery
# --------------------------------------------------------------------------- #
def _state(ctx: ScenarioContext) -> dict[str, Any]:
    if not isinstance(ctx.data, dict):
        ctx.data = {
            "pending": [],  # (file name, csv content) fixtures from Given steps
            "restart": False,  # a restart between the Givens and the When
            "broken_context": False,  # AC-10: the context cannot be built
            "contexts": {},  # dataset -> WorkspaceContext the cataloguer got
            "repo": None,
        }
    return ctx.data


class _SpyCataloguer:
    """Records the context each cataloguing received; output == offline path."""

    def __init__(self, recorder: dict[str, Any]):
        self.recorder = recorder
        self.store = None  # attached after the repository is built

    def catalog(self, payload, relationships=(), context=None):  # noqa: ANN001
        from analyst.agentic import enrich

        self.recorder[payload.dataset] = context
        return enrich.catalog_entry(
            payload.dataset,
            self.store.profile(payload.dataset),
            relationships,
            context=context,
        )


def _build_repo(ctx: ScenarioContext, flavor: str, data_dir: Path):  # noqa: ANN202
    from analyst.api.repository import StoreRepository

    st = _state(ctx)
    if flavor == "spy":
        spy = _SpyCataloguer(st["contexts"])
        repo = StoreRepository(str(data_dir), cataloguer=spy)
        spy.store = repo.store
    elif flavor == "offline":
        repo = StoreRepository(str(data_dir))
    elif flavor == "llm":
        from analyst.agentic.cataloguer import Cataloguer
        from analyst.agentic.gateway import LLMGateway, ReplayBackend

        repo = StoreRepository(
            str(data_dir),
            cataloguer=Cataloguer(LLMGateway(ReplayBackend(CONTEXT_CASSETTE))),
        )
    else:  # pragma: no cover - guarded by the step vocabulary
        raise AssertionError(f"unknown cataloguer flavor {flavor!r}")
    if st["broken_context"]:

        def _broken():
            raise RuntimeError("catalog registry unavailable")

        repo.service.catalog_source = _broken
    if st.get("broken_retro"):

        def _boom(*args, **kwargs):  # noqa: ANN002, ANN003
            raise RuntimeError("re-derivation failed")

        repo._derive_entry = _boom
    return repo


def _realize(ctx: ScenarioContext, flavor: str = "spy"):  # noqa: ANN202
    """Ingest the Given fixtures (honoring a restart), return the live repo."""
    st = _state(ctx)
    data_dir = ctx.tmp_path / "data"
    repo = _build_repo(ctx, flavor, data_dir)
    for name, content in st["pending"]:
        repo.ingest(name, content.encode("utf-8"))
    st["pending"] = []
    # Snapshot the Given-time entries, for "unchanged"/"prior" assertions.
    st["prior"] = {n: r.summary.catalog for n, r in repo._records.items()}
    if st["restart"]:
        repo = _build_repo(ctx, flavor, data_dir)  # fresh session, same disk
        st["restart"] = False
    st["repo"] = repo
    return repo


def _repo(ctx: ScenarioContext):  # noqa: ANN202
    st = _state(ctx)
    assert st["repo"] is not None, "no repository realized yet"
    return st["repo"]


def _record(ctx: ScenarioContext, table: str):  # noqa: ANN202
    repo = _repo(ctx)
    match = repo.get_dataset(table) or repo.get_dataset(f"{table}.csv")
    assert match is not None, f"dataset {table!r} not found"
    return match


def _entry(ctx: ScenarioContext, table: str):  # noqa: ANN202
    entry = _record(ctx, table).summary.catalog
    assert entry is not None, f"{table!r} has no catalog entry"
    return entry


def _context_for(ctx: ScenarioContext, table: str):  # noqa: ANN202
    contexts = _state(ctx)["contexts"]
    for key in (table, f"{table}.csv"):
        if key in contexts:
            return contexts[key]
    raise AssertionError(
        f"no cataloguing context recorded for {table!r} (have {sorted(contexts)})"
    )


def _sibling(context, table: str):  # noqa: ANN001, ANN202
    for t in context.tables:
        if t.name in (table, f"{table}.csv"):
            return t
    raise AssertionError(
        f"table {table!r} not in context ({[t.name for t in context.tables]})"
    )


def _first_sentence(text: str) -> str:
    head = text.split(". ", 1)[0].strip()
    return head if head.endswith(".") else head + "."


# --------------------------------------------------------------------------- #
# Given — fixture intent
# --------------------------------------------------------------------------- #
@step(r'a workspace with a catalogued file "customers\.csv" keyed by "id"')
def given_customers(ctx: ScenarioContext) -> None:
    _state(ctx)["pending"].append(("customers.csv", CUSTOMERS_CSV))


@step(
    r'a workspace with catalogued files "customers\.csv" keyed by "id" '
    r'and "products\.csv" keyed by "sku"'
)
def given_customers_and_products(ctx: ScenarioContext) -> None:
    _state(ctx)["pending"].append(("customers.csv", CUSTOMERS_CSV))
    _state(ctx)["pending"].append(("products.csv", PRODUCTS_CSV))


@step(r'a workspace with a catalogued file "orders\.csv" with a column "customer_id"')
def given_orders(ctx: ScenarioContext) -> None:
    _state(ctx)["pending"].append(("orders.csv", ORDERS_CSV))


@step(r"the service restarts")
def given_restart(ctx: ScenarioContext) -> None:
    _state(ctx)["restart"] = True


@step(r"the workspace context cannot be built")
def given_broken_context(ctx: ScenarioContext) -> None:
    _state(ctx)["broken_context"] = True


@step(r"re-cataloguing of existing tables is failing")
def given_broken_retro(ctx: ScenarioContext) -> None:
    _state(ctx)["broken_retro"] = True


@step(r"a connected database whose tables are catalogued")
def given_connected_catalogued(ctx: ScenarioContext) -> None:
    db_path = _two_table_sqlite(ctx)
    _state(ctx)["db_path"] = db_path
    _realize(ctx, "spy")  # empty file workspace, real repo on disk
    _connect_crm(ctx, db_path)
    _state(ctx)["snapshot"] = {
        r.name: r.summary.catalog.table_description
        for r in _repo(ctx).list_datasets()
        if r.name.startswith("crm.")
    }


@step(r"the schema of one table changes while the service is down")
def given_schema_changed(ctx: ScenarioContext) -> None:
    db_path = _state(ctx)["db_path"]
    con = sqlite3.connect(db_path)
    con.execute("ALTER TABLE customers ADD COLUMN tier TEXT")
    con.execute("UPDATE customers SET tier = 'gold'")
    con.commit()
    con.close()


# --------------------------------------------------------------------------- #
# When — realize the workspace and act
# --------------------------------------------------------------------------- #
@step(
    r'a file "orders\.csv" whose "customer_id" values all match "customers\.id" is ingested'
)
def when_orders_ingested(ctx: ScenarioContext) -> None:
    _realize(ctx, "spy").ingest("orders.csv", ORDERS_CSV.encode("utf-8"))


@step(
    r'a file "orders\.csv" whose "customer_id" values all match "customers\.id" '
    r"is ingested with the offline cataloguer"
)
def when_orders_ingested_offline(ctx: ScenarioContext) -> None:
    _realize(ctx, "offline").ingest("orders.csv", ORDERS_CSV.encode("utf-8"))


@step(
    r'a file "orders\.csv" whose "customer_id" values all match "customers\.id" '
    r"is ingested with the language-model cataloguer"
)
def when_orders_ingested_llm(ctx: ScenarioContext) -> None:
    _realize(ctx, "llm").ingest("orders.csv", ORDERS_CSV.encode("utf-8"))


@step(
    r'a file "orders\.csv" whose "customer_id" values all match "customers\.id" '
    r"is ingested twice into identical workspaces"
)
def when_orders_ingested_twice(ctx: ScenarioContext) -> None:
    from analyst.api.repository import StoreRepository

    st = _state(ctx)
    entries = []
    for run in ("a", "b"):
        repo = StoreRepository(str(ctx.tmp_path / run / "data"))
        for name, content in st["pending"]:
            repo.ingest(name, content.encode("utf-8"))
        (orders,) = repo.ingest("orders.csv", ORDERS_CSV.encode("utf-8"))
        entries.append(orders.summary.catalog)
    st["pending"] = []
    st["twin_entries"] = entries


def _customers_sqlite(ctx: ScenarioContext) -> Path:
    path = ctx.tmp_path / "db" / "crm.sqlite"
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE customers (customer_id INTEGER PRIMARY KEY, region TEXT)")
    con.executemany(
        "INSERT INTO customers VALUES (?, ?)", [(10, "North"), (20, "South")]
    )
    con.commit()
    con.close()
    return path


def _two_table_sqlite(ctx: ScenarioContext) -> Path:
    path = ctx.tmp_path / "db" / "crm.sqlite"
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE customers (customer_id INTEGER PRIMARY KEY, region TEXT)")
    con.executemany(
        "INSERT INTO customers VALUES (?, ?)", [(10, "North"), (20, "South")]
    )
    con.execute("CREATE TABLE products (sku TEXT PRIMARY KEY, label TEXT)")
    con.executemany(
        "INSERT INTO products VALUES (?, ?)", [("A1", "Widget"), ("B2", "Gadget")]
    )
    con.commit()
    con.close()
    return path


def _connect_crm(ctx: ScenarioContext, db_path: Path):  # noqa: ANN202
    """Connect the crm SQLite through a spy catalog_fn; drain; return manager."""
    from analyst.api.routes.databases import DatabaseManager, _enrich_catalog_fn
    from analyst.domain.connection import ConnectionSpec, DatabaseEngine

    repo = _repo(ctx)
    recorder: dict[str, Any] = {}
    _state(ctx)["rederived"] = recorder

    def spy_fn(table, relationships, context):  # noqa: ANN001
        recorder[table.name] = context
        return _enrich_catalog_fn(table, relationships, context)

    manager = DatabaseManager(repo=repo, catalog_fn=spy_fn)
    _state(ctx)["manager"] = manager
    manager.connect(
        ConnectionSpec(name="crm", engine=DatabaseEngine.SQLITE, path=str(db_path))
    )
    if manager._pool is not None:
        manager._pool.shutdown(wait=True)
        manager._pool = None
    return manager


@step(r'a database whose table "customers" is keyed by "customer_id" is connected')
def when_database_connected(ctx: ScenarioContext) -> None:
    from analyst.api.routes.databases import DatabaseManager, _enrich_catalog_fn
    from analyst.domain.connection import ConnectionSpec, DatabaseEngine

    repo = _realize(ctx, "spy")
    recorder = _state(ctx)["contexts"]

    def spy_fn(table, relationships, context):  # noqa: ANN001
        recorder[table.name] = context
        return _enrich_catalog_fn(table, relationships, context)

    manager = DatabaseManager(repo=repo, catalog_fn=spy_fn)
    _state(ctx)["manager"] = manager
    manager.connect(
        ConnectionSpec(
            name="crm",
            engine=DatabaseEngine.SQLITE,
            path=str(_customers_sqlite(ctx)),
        )
    )
    manager._pool.shutdown(wait=True)  # drain background cataloguing
    manager._pool = None


# --------------------------------------------------------------------------- #
# Then — context contents (AC-1, AC-8)
# --------------------------------------------------------------------------- #
@step(
    r'the cataloguing context for "(?P<table>[^"]+)" names the table "(?P<other>[^"]+)" with its description'
)
def then_context_names_table(ctx: ScenarioContext, table: str, other: str) -> None:
    sibling = _sibling(_context_for(ctx, table), other)
    assert sibling.description, f"{other!r} carries no description in the context"


@step(
    r'the cataloguing context for "(?P<table>[^"]+)" includes the columns of "(?P<other>[^"]+)"'
)
def then_context_includes_columns(ctx: ScenarioContext, table: str, other: str) -> None:
    sibling = _sibling(_context_for(ctx, table), other)
    assert sibling.columns, f"{other!r} carries no columns in the context"


@step(
    r'the cataloguing context for "(?P<table>[^"]+)" does not include the columns of "(?P<other>[^"]+)"'
)
def then_context_excludes_columns(ctx: ScenarioContext, table: str, other: str) -> None:
    sibling = _sibling(_context_for(ctx, table), other)
    assert sibling.columns == (), (
        f"{other!r} is not directly related yet its columns are in the context"
    )


@step(
    r'the cataloguing context for "(?P<table>[^"]+)" includes the relationship between "(?P<child>[^"]+)" and "(?P<parent>[^"]+)"'
)
def then_context_includes_relationship(
    ctx: ScenarioContext, table: str, child: str, parent: str
) -> None:
    context = _context_for(ctx, table)
    assert any(
        r.child_table in (child, f"{child}.csv")
        and r.parent_table in (parent, f"{parent}.csv")
        for r in context.relationships
    ), f"no {child}->{parent} relationship in the context"


@step(r"the cataloguing context contains no data rows")
def then_context_has_no_rows(ctx: ScenarioContext) -> None:
    context = _context_for(ctx, "orders")
    # Metadata-only by construction: the types can hold nothing row-shaped.
    from analyst.domain.catalog import ColumnDescription
    from analyst.domain.workspace_context import TableContext, WorkspaceContext

    assert {f.name for f in dataclasses.fields(WorkspaceContext)} == {
        "tables",
        "relationships",
    }
    assert {f.name for f in dataclasses.fields(TableContext)} == {
        "name",
        "description",
        "columns",
    }
    for t in context.tables:
        assert all(isinstance(c, ColumnDescription) for c in t.columns)


@step(
    r"the cataloguing context carries only names, descriptions, roles, and relationships"
)
def then_context_is_metadata_only(ctx: ScenarioContext) -> None:
    from analyst.domain.catalog import ColumnDescription

    context = _context_for(ctx, "orders")
    for t in context.tables:
        assert isinstance(t.name, str) and isinstance(t.description, str)
        for c in t.columns:
            assert isinstance(c, ColumnDescription)
            assert isinstance(c.name, str)
            assert isinstance(c.description, str)
            assert isinstance(c.role, str)


# --------------------------------------------------------------------------- #
# Then — derived meaning (AC-2, AC-3, AC-11)
# --------------------------------------------------------------------------- #
@step(
    r'the description of column "(?P<column>[^"]+)" of "(?P<table>[^"]+)" references the meaning of "(?P<other>[^"]+)"'
)
def then_column_references_meaning(
    ctx: ScenarioContext, column: str, table: str, other: str
) -> None:
    entry = _entry(ctx, table)
    col = next(c for c in entry.columns if c.name == column)
    parent = _entry(ctx, other)
    meaning = _first_sentence(parent.table_description)
    assert meaning in col.description, (
        f"{column!r} does not carry {other!r}'s meaning ({meaning!r}): "
        f"{col.description!r}"
    )


@step(r'the description of "(?P<table>[^"]+)" references "(?P<other>[^"]+)"')
def then_table_references(ctx: ScenarioContext, table: str, other: str) -> None:
    description = _entry(ctx, table).table_description
    assert other in description or f"{other}.csv" in description, (
        f"{table!r} does not reference {other!r}: {description!r}"
    )


# --------------------------------------------------------------------------- #
# Then — determinism (AC-9) + containment (AC-10)
# --------------------------------------------------------------------------- #
@step(r'both runs derive identical descriptions for "orders"')
def then_runs_identical(ctx: ScenarioContext) -> None:
    a, b = _state(ctx)["twin_entries"]
    assert a == b, "workspace-aware cataloguing diverged between identical runs"


@step(r'the ingestion of "orders" succeeds')
def then_ingestion_succeeded(ctx: ScenarioContext) -> None:
    assert _entry(ctx, "orders") is not None


# --------------------------------------------------------------------------- #
# Then — retroactive re-cataloguing (AC-4, AC-5, AC-10)
# --------------------------------------------------------------------------- #
@step(
    r'the description of "(?P<table>[^"]+)" states it is referenced by "(?P<child>[^"]+)"'
)
def then_table_referenced_by(ctx: ScenarioContext, table: str, child: str) -> None:
    description = _entry(ctx, table).table_description
    assert f"Referenced by {child}" in description or (
        f"Referenced by {child}.csv" in description
    ), f"{table!r} does not state it is referenced by {child!r}: {description!r}"


@step(r'the description of "(?P<table>[^"]+)" states it references "(?P<parent>[^"]+)"')
def then_table_states_references(ctx: ScenarioContext, table: str, parent: str) -> None:
    description = _entry(ctx, table).table_description
    assert "References" in description and parent in description, (
        f"{table!r} does not state it references {parent!r}: {description!r}"
    )


@step(
    r'the description of "(?P<table>[^"]+)" reflects its new relationship to "(?P<child>[^"]+)"'
)
def then_table_reflects_new_relationship(
    ctx: ScenarioContext, table: str, child: str
) -> None:
    then_table_referenced_by(ctx, table=table, child=child)


@step(r'the catalog entry of "(?P<table>[^"]+)" is unchanged from before the ingestion')
def then_entry_unchanged(ctx: ScenarioContext, table: str) -> None:
    prior = _state(ctx)["prior"].get(f"{table}.csv") or _state(ctx)["prior"].get(table)
    assert prior is not None, f"no prior entry snapshot for {table!r}"
    assert _entry(ctx, table) == prior, f"{table!r} was re-derived"


@step(r'the description of "(?P<table>[^"]+)" remains its prior catalog entry')
def then_entry_remains_prior(ctx: ScenarioContext, table: str) -> None:
    then_entry_unchanged(ctx, table=table)


# --------------------------------------------------------------------------- #
# Connected-database persistence across sessions (AC-6, AC-7)
# --------------------------------------------------------------------------- #
@step(r"the service restarts and the database is reconnected")
def when_restart_and_reconnect(ctx: ScenarioContext) -> None:
    from analyst.api.repository import StoreRepository

    st = _state(ctx)
    st["manager"].close()
    st["repo"] = StoreRepository(str(ctx.tmp_path / "data"))  # fresh session
    st["restart"] = False
    _connect_crm(ctx, st["db_path"])  # resets st["rederived"] to this session


@step(
    r"each table of the connected database still has its description after the restart"
)
def then_persisted_descriptions_survive(ctx: ScenarioContext) -> None:
    from analyst.api.repository import StoreRepository

    st = _state(ctx)
    fresh = StoreRepository(str(ctx.tmp_path / "data"))  # a fresh session's view
    for name, description in st["snapshot"].items():
        loaded = fresh.load_persisted_catalog(name)
        assert loaded is not None, f"no persisted catalog for {name!r}"
        entry, _fingerprint = loaded
        assert entry.table_description == description, (
            f"persisted description for {name!r} drifted"
        )


@step(r"the tables immediately show the same descriptions they had before the restart")
def then_reconnect_reuses(ctx: ScenarioContext) -> None:
    st = _state(ctx)
    assert not st["rederived"], (
        f"tables were re-derived on reconnect: {sorted(st['rederived'])}"
    )
    for name, description in st["snapshot"].items():
        record = _repo(ctx).get_dataset(name)
        assert record is not None, f"{name!r} missing after reconnect"
        assert record.catalog_status == "complete"
        assert record.summary.catalog.table_description == description


@step(r"the changed table is re-catalogued")
def then_changed_table_rederived(ctx: ScenarioContext) -> None:
    st = _state(ctx)
    assert "customers" in st["rederived"], "the changed table was not re-catalogued"
    entry = _repo(ctx).get_dataset("crm.customers").summary.catalog
    assert "tier" in {c.name for c in entry.columns}


@step(r"the unchanged tables keep their persisted descriptions")
def then_unchanged_tables_kept(ctx: ScenarioContext) -> None:
    st = _state(ctx)
    assert "products" not in st["rederived"], "an unchanged table was re-derived"
    record = _repo(ctx).get_dataset("crm.products")
    assert record.summary.catalog.table_description == st["snapshot"]["crm.products"]


@step(r'"orders" has a description derived without workspace context')
def then_orders_in_isolation(ctx: ScenarioContext) -> None:
    entry = _entry(ctx, "orders")
    fk = next(c for c in entry.columns if c.name == "customer_id")
    # Name-level grounding stays; the sibling's woven meaning must be absent.
    assert "customers.csv" in fk.description
    assert "rows" not in fk.description
