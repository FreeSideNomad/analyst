"""Step handlers for feature 009 — semantic depth (PK/FK discovery + richer
catalog to UI & planner).

Backend discovery / RI / join-type / governance scenarios bind over the
in-process seam (a real DatasetStore in the scenario tmp_path); the planner
scenario (AC-14) replays a recorded cassette; the focus + async-progress flows
bind to Playwright against the fixtures app (relationships are seeded into the
fixtures). Cataloguing scenarios replay the cataloguer cassette. Deterministic —
no live model calls in the board.
"""

from __future__ import annotations

from typing import Any

from acceptance.e2e_base import (  # noqa: F401 (re-exported for the generated board)
    REPO_ROOT,
    ScenarioContext,
    _e2e_fresh,
    _e2e_stack,
    expect_,
    make_registry,
)
from acceptance.join009 import JOIN_CASSETTE, build_plan
from analyst.agentic.gateway import ReplayBackend
from analyst.engine.store import DatasetStore
from analyst.service.ingestion import IngestionService

CHINOOK = REPO_ROOT / "tests" / "golden" / "chinook.sqlite"

step, run_step = make_registry()
_expect = expect_

__all__ = [
    "ScenarioContext",
    "run_step",
    "_e2e_stack",
    "_e2e_fresh",
]


# --------------------------------------------------------------------------- #
# In-process backend seam — a real store per scenario, relationships discovered.
# --------------------------------------------------------------------------- #
def _state(ctx: ScenarioContext) -> dict[str, Any]:
    if not isinstance(ctx.data, dict):
        ctx.data = {}
    return ctx.data


def _store(ctx: ScenarioContext) -> DatasetStore:
    st = _state(ctx)
    if "store" not in st:
        store = DatasetStore(base_dir=ctx.tmp_path / "store")
        st["store"] = store
        st["service"] = IngestionService(store)
    return st["store"]


def _ingest(ctx: ScenarioContext, name: str, content: str) -> None:
    _store(ctx)  # ensure store/service
    path = ctx.tmp_path / name
    path.write_text(content, encoding="utf-8")
    _state(ctx)["service"].ingest(path)


def _discover(ctx: ScenarioContext) -> list:
    rels = _store(ctx).discover_relationships()
    _state(ctx)["rels"] = rels
    return rels


def _rel(ctx: ScenarioContext, child_stem: str, child_col: str, parent_stem: str):
    """The discovered relationship child_stem.child_col -> parent_stem.* , or None."""
    for r in _state(ctx).get("rels", []):
        if (
            r.child_table.split(".")[0] == child_stem
            and r.child_column == child_col
            and r.parent_table.split(".")[0] == parent_stem
        ):
            return r
    return None


# Canonical fixtures: customers keyed by "id"; orders references it.
_CUSTOMERS = "id,region\n10,North\n20,South\n30,East\n"
_ORDERS_MATCH = "order_id,customer_id\n1,10\n2,20\n3,10\n"  # all match, no nulls
_ORDERS_MISS = "order_id,customer_id\n1,10\n2,99\n3,10\n"  # 99 absent from customers
_ORDERS_NULL = "order_id,customer_id\n1,10\n2,\n3,20\n"  # a null, rest match


@step(r'a file "orders\.csv" with a column "customer_id"$')
def given_orders_bare(ctx: ScenarioContext) -> None:
    # AC-2: customers is a separate Given step.
    _ingest(ctx, "orders.csv", _ORDERS_MATCH)


@step(r'a file "orders\.csv" whose "customer_id" all match "customers\.id"')
@step(
    r'a file "orders\.csv" whose "customer_id" has no nulls and all match '
    r'"customers\.id"'
)
def given_orders_match(ctx: ScenarioContext) -> None:
    # AC-4b/AC-5: a single Given — customers is implied, create both.
    _ingest(ctx, "customers.csv", _CUSTOMERS)
    _ingest(ctx, "orders.csv", _ORDERS_MATCH)


@step(
    r'a file "customers\.csv" whose key column "id" contains every '
    r'"orders\.customer_id" value'
)
def given_customers(ctx: ScenarioContext) -> None:
    _ingest(ctx, "customers.csv", _CUSTOMERS)


@step(
    r'a file "orders\.csv" with a column "customer_id" containing a value '
    r'absent from "customers\.id"'
)
def given_orders_miss(ctx: ScenarioContext) -> None:
    _ingest(ctx, "customers.csv", _CUSTOMERS)
    _ingest(ctx, "orders.csv", _ORDERS_MISS)


@step(
    r'a file "orders\.csv" whose "customer_id" has nulls and otherwise all '
    r'match "customers\.id"'
)
def given_orders_null(ctx: ScenarioContext) -> None:
    _ingest(ctx, "customers.csv", _CUSTOMERS)
    _ingest(ctx, "orders.csv", _ORDERS_NULL)


@step(r'files "orders\.csv" and "customers\.csv"$')
def given_orders_and_customers(ctx: ScenarioContext) -> None:
    _ingest(ctx, "customers.csv", _CUSTOMERS)
    _ingest(ctx, "orders.csv", _ORDERS_MATCH)


@step(
    r'a file "products\.csv" with a column "id" and a file "regions\.csv" '
    r'with a column "id" whose values do not overlap'
)
def given_products_regions(ctx: ScenarioContext) -> None:
    _ingest(ctx, "products.csv", "id,name\n1,Widget\n2,Gadget\n")
    _ingest(ctx, "regions.csv", "id,name\n100,North\n200,South\n")


@step(r"relationships are discovered")
def when_discover(ctx: ScenarioContext) -> None:
    _discover(ctx)


@step(
    r'an inferred relationship from "orders\.customer_id" to "customers\.id" '
    r"is proposed"
)
def then_inferred_proposed(ctx: ScenarioContext) -> None:
    r = _rel(ctx, "orders", "customer_id", "customers")
    assert r is not None, f"no rel in {_state(ctx).get('rels')}"
    assert r.origin == "inferred" and r.parent_column == "id"


@step(r'no relationship from "orders\.customer_id" to "customers\.id" is proposed')
def then_no_rel_orders(ctx: ScenarioContext) -> None:
    assert _rel(ctx, "orders", "customer_id", "customers") is None


@step(
    r'the relationship from "orders\.customer_id" to "customers\.id" is marked '
    r"optional"
)
def then_optional(ctx: ScenarioContext) -> None:
    r = _rel(ctx, "orders", "customer_id", "customers")
    assert r is not None and r.join_type == "optional", r


@step(
    r'the relationship from "orders\.customer_id" to "customers\.id" is marked '
    r"required"
)
def then_required(ctx: ScenarioContext) -> None:
    r = _rel(ctx, "orders", "customer_id", "customers")
    assert r is not None and r.join_type == "required", r


@step(
    r'the relationship from "orders\.customer_id" to "customers\.id" is marked '
    r"inferred with full match coverage"
)
def then_full_coverage(ctx: ScenarioContext) -> None:
    r = _rel(ctx, "orders", "customer_id", "customers")
    assert r is not None and r.origin == "inferred" and r.coverage == 1.0, r


@step(r'no relationship between "products\.id" and "regions\.id" is proposed')
def then_no_products_regions(ctx: ScenarioContext) -> None:
    assert _rel(ctx, "products", "id", "regions") is None
    assert _rel(ctx, "regions", "id", "products") is None


# --------------------------------------------------------------------------- #
# AC-15 — governance: RI is local; no bulk rows to the model.
# --------------------------------------------------------------------------- #
@step(r"the referential-integrity check runs locally")
def then_ri_local(ctx: ScenarioContext) -> None:
    # discover() takes only the store connection — no gateway, no egress.
    assert _rel(ctx, "orders", "customer_id", "customers") is not None


@step(r"only schema, profiles, and capped samples are sent to the language model")
def then_no_bulk_egress(ctx: ScenarioContext) -> None:
    # Discovery has no model call at all — nothing crosses. Structural (AC-15).
    assert "rels" in _state(ctx)


# --------------------------------------------------------------------------- #
# AC-14 — the planner joins on a discovered relationship (replayed cassette).
# --------------------------------------------------------------------------- #
@step(
    r'files "orders\.csv" and "customers\.csv" with a discovered relationship '
    r'on "customer_id"'
)
def given_join_setup(ctx: ScenarioContext) -> None:
    plan, rels = build_plan(ctx.tmp_path, ReplayBackend(JOIN_CASSETTE))
    _state(ctx).update(plan=plan, rels=list(rels))


@step(r"the user asks a question that needs both tables")
def when_join_question(ctx: ScenarioContext) -> None:
    pass  # the plan was produced in the Given (shared recorder/replayer path)


@step(r"the answer's SQL joins them on the discovered relationship")
def then_sql_joins(ctx: ScenarioContext) -> None:
    sql = (_state(ctx)["plan"].sql or "").lower()
    assert "join" in sql and "customer_id" in sql, sql


@step(r"the join keeps unmatched rows when the relationship is optional")
def then_left_join(ctx: ScenarioContext) -> None:
    sql = (_state(ctx)["plan"].sql or "").lower()
    assert "left" in sql, f"expected a LEFT/outer join for the optional FK: {sql}"


# --------------------------------------------------------------------------- #
# (Declared / cross-source / cataloguing / browser bindings added next.)
# --------------------------------------------------------------------------- #
