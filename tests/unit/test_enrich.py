"""Feature 009 — data-grounded catalog enrichment (AC-8, AC-9)."""

from __future__ import annotations

from analyst.agentic.enrich import catalog_entry
from analyst.domain.profile import ColumnProfile, DatasetProfile
from analyst.domain.relationships import INFERRED, OPTIONAL, REQUIRED, Relationship
from analyst.domain.types import ColumnType

T = ColumnType

_STUB = "Text column from the source table."


def _district_profile() -> DatasetProfile:
    return DatasetProfile(
        row_count=603,
        columns=(
            ColumnProfile(
                "address_id", T.INTEGER, 0, 603, (1, 2, 3), minimum=1, maximum=603
            ),
            ColumnProfile(
                "district",
                T.TEXT,
                0,
                20,
                ("California", "England", "Texas"),
            ),
        ),
    )


def test_column_description_is_grounded_not_generic():
    entry = catalog_entry("address", _district_profile())
    district = next(c for c in entry.columns if c.name == "district")
    assert district.description != _STUB
    # Specific to its values / cardinality.
    assert "California" in district.description
    assert "20" in district.description


def test_table_description_aggregates_relationships():
    profile = DatasetProfile(
        row_count=1000,
        columns=(
            ColumnProfile("order_id", T.INTEGER, 0, 1000, (1, 2, 3)),
            ColumnProfile("customer_id", T.INTEGER, 0, 800, (1, 2, 3)),
            ColumnProfile("product_id", T.INTEGER, 0, 500, (1, 2, 3)),
        ),
    )
    rels = (
        Relationship(
            "orders", "customer_id", "customers", "id", INFERRED, REQUIRED, 1.0
        ),
        Relationship("orders", "product_id", "products", "id", INFERRED, OPTIONAL, 1.0),
    )
    entry = catalog_entry("orders", profile, rels)
    assert "customers" in entry.table_description
    assert "products" in entry.table_description
    # FK columns become identifiers with a reference description.
    cust = next(c for c in entry.columns if c.name == "customer_id")
    assert cust.role == "identifier"
    assert "customers" in cust.description
    # Optional FK is described as optional.
    prod = next(c for c in entry.columns if c.name == "product_id")
    assert "optional" in prod.description
    assert entry.relationships == rels
