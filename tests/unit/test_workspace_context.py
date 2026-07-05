"""Feature 010 — WorkspaceContext: build, trim, determinism, metadata-only."""

from __future__ import annotations

import dataclasses

from analyst.domain.catalog import CatalogEntry, ColumnDescription
from analyst.domain.relationships import INFERRED, REQUIRED, Relationship
from analyst.domain.workspace_context import (
    TableContext,
    WorkspaceContext,
    build_workspace_context,
)

_CUSTOMERS = CatalogEntry(
    table_description="customers.csv: 2 rows, 2 columns. Customer master.",
    columns=(
        ColumnDescription("id", "Primary key of the table.", "identifier"),
        ColumnDescription("region", "Categorical region.", "category"),
    ),
)
_PRODUCTS = CatalogEntry(
    table_description="products.csv: 5 rows, 2 columns.",
    columns=(
        ColumnDescription("sku", "Primary key of the table.", "identifier"),
        ColumnDescription("label", "Text label.", "text"),
    ),
)
_REL = Relationship(
    "orders.csv", "customer_id", "customers.csv", "id", INFERRED, REQUIRED, 1.0
)


def _build() -> WorkspaceContext:
    return build_workspace_context(
        {"customers.csv": _CUSTOMERS, "products.csv": _PRODUCTS, "broken.csv": None},
        (_REL,),
    )


def test_build_carries_names_descriptions_and_columns():
    ctx = _build()
    names = [t.name for t in ctx.tables]
    assert names == sorted(names)
    assert set(names) == {"customers.csv", "products.csv"}  # None catalog skipped
    customers = next(t for t in ctx.tables if t.name == "customers.csv")
    assert "Customer master" in customers.description
    assert [c.name for c in customers.columns] == ["id", "region"]
    assert ctx.relationships == (_REL,)


def test_for_table_trims_columns_to_direct_links_and_drops_self():
    view = _build().for_table("orders.csv")
    names = {t.name for t in view.tables}
    assert "orders.csv" not in names
    customers = next(t for t in view.tables if t.name == "customers.csv")
    products = next(t for t in view.tables if t.name == "products.csv")
    assert customers.columns  # directly linked -> columns kept
    assert products.columns == ()  # unrelated -> name + description only
    assert "products.csv" in {t.name for t in view.tables}


def test_describe_returns_the_sibling_description():
    ctx = _build()
    assert "Customer master" in (ctx.describe("customers.csv") or "")
    assert ctx.describe("nope.csv") is None


def test_build_is_deterministic_regardless_of_mapping_order():
    a = build_workspace_context(
        {"customers.csv": _CUSTOMERS, "products.csv": _PRODUCTS}, (_REL,)
    )
    b = build_workspace_context(
        {"products.csv": _PRODUCTS, "customers.csv": _CUSTOMERS}, (_REL,)
    )
    assert a == b


def test_context_is_metadata_only_by_construction():
    # The type can hold only names, descriptions, roles, relationships —
    # assert the field surface so a row-shaped field can't sneak in (AC-8).
    assert {f.name for f in dataclasses.fields(TableContext)} == {
        "name",
        "description",
        "columns",
    }
    assert {f.name for f in dataclasses.fields(WorkspaceContext)} == {
        "tables",
        "relationships",
    }
