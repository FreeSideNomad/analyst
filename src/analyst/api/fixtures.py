"""Fixtures — the mock, relocated into Python and built from the real domain.

Each dataset is a genuine `DatasetSummary` (DatasetProfile + CatalogEntry made of
ColumnProfile / ColumnDescription / Clarification). Because these are the same
frozen dataclasses the engine produces, the fixtures cannot drift from the wire
contract — a domain change breaks them at type-check time.

This is the single source of demo data (previously duplicated in the TS app).
"""

from __future__ import annotations


from analyst.domain.catalog import CatalogEntry, Clarification, ColumnDescription
from analyst.domain.dataset import DatasetSummary
from analyst.domain.profile import ColumnProfile, DatasetProfile
from analyst.domain.types import ColumnType

T = ColumnType


def _col(
    name: str,
    itype: ColumnType,
    null_count: int,
    distinct: int,
    samples: tuple[object, ...],
    *,
    minimum: object | None = None,
    maximum: object | None = None,
    quantiles: tuple[object, ...] = (),
    is_mixed: bool = False,
    dominant: ColumnType | None = None,
    off_type: tuple[object, ...] = (),
    is_nested: bool = False,
) -> ColumnProfile:
    return ColumnProfile(
        name=name,
        inferred_type=itype,
        null_count=null_count,
        distinct_count=distinct,
        samples=samples,
        minimum=minimum,
        maximum=maximum,
        quantiles=quantiles,
        is_mixed=is_mixed,
        dominant_type=dominant,
        off_type_examples=off_type,
        is_nested=is_nested,
    )


def _describe(*rows: tuple[str, str, str]) -> tuple[ColumnDescription, ...]:
    return tuple(ColumnDescription(name=n, description=d, role=r) for n, d, r in rows)


# --------------------------------------------------------------------------- sales
_SALES = DatasetSummary(
    name="sales",
    profile=DatasetProfile(
        row_count=143209,
        columns=(
            _col(
                "order_id",
                T.TEXT,
                0,
                143209,
                ("ORD-100001", "ORD-100002", "ORD-100003"),
            ),
            _col(
                "order_date",
                T.DATE,
                12,
                365,
                ("2024-01-15", "2024-03-22", "2024-07-04"),
            ),
            _col(
                "customer_id", T.TEXT, 0, 11204, ("CUST-2001", "CUST-5832", "CUST-9104")
            ),
            _col("product_id", T.TEXT, 0, 1847, ("PROD-101", "PROD-422", "PROD-780")),
            _col(
                "quantity",
                T.INTEGER,
                0,
                48,
                (1, 3, 12),
                minimum=1,
                maximum=50,
                quantiles=(1, 3, 5),
            ),
            _col(
                "unit_price",
                T.DECIMAL,
                0,
                320,
                (9.99, 49.95, 249.0),
                minimum=0.99,
                maximum=1299.99,
                quantiles=(19.99, 49.95, 99.99),
            ),
            _col("billing_region", T.TEXT, 237, 4, ("North", "South", "East")),
            _col("channel", T.TEXT, 0, 3, ("online", "retail", "wholesale")),
        ),
        encoding="utf-8",
        synthesized_headers=False,
        had_duplicate_columns=False,
    ),
    catalog=CatalogEntry(
        table_description=(
            "Transactional sales orders for FY2024 across online, retail and "
            "wholesale channels."
        ),
        columns=_describe(
            ("order_id", "Unique order identifier.", "identifier"),
            ("order_date", "Date the order was placed.", "timestamp"),
            ("customer_id", "References a customer record.", "identifier"),
            ("product_id", "References a product record.", "identifier"),
            ("quantity", "Number of units ordered.", "measure"),
            ("unit_price", "Price per unit at time of sale.", "measure"),
            ("billing_region", "Region from the billing address.", "category"),
            ("channel", "Sales channel: online, retail, wholesale.", "category"),
        ),
        clarifications=(),
    ),
)

# ----------------------------------------------------------------------- customers
_CUSTOMERS = DatasetSummary(
    name="customers",
    profile=DatasetProfile(
        row_count=12488,
        columns=(
            _col(
                "customer_id", T.TEXT, 0, 12488, ("CUST-2001", "CUST-5832", "CUST-9104")
            ),
            _col(
                "customer_name",
                T.TEXT,
                3,
                12420,
                ("Acme Corp", "Globex Inc", "Initech LLC"),
            ),
            _col("email", T.TEXT, 45, 12340, ("john@acme.co", "jane@globex.com", None)),
            _col("region", T.TEXT, 0, 4, ("North", "South", "East")),
            _col(
                "signup_date",
                T.DATE,
                0,
                1820,
                ("2019-06-01", "2021-11-15", "2023-02-28"),
            ),
            _col(
                "lifetime_value",
                T.DECIMAL,
                128,
                9870,
                (1250.0, 89.5, 34200.0),
                minimum=0,
                maximum=182450.0,
                quantiles=(980.0, 4350.0, 11200.0),
            ),
        ),
        encoding="utf-8",
    ),
    catalog=CatalogEntry(
        table_description=(
            "Master customer records: contact info, region and calculated "
            "lifetime value."
        ),
        columns=_describe(
            ("customer_id", "Unique customer identifier.", "identifier"),
            ("customer_name", "Company or individual name.", "text"),
            ("email", "Primary contact email.", "text"),
            ("region", "Geographic region of the customer.", "category"),
            ("signup_date", "Account creation date.", "timestamp"),
            ("lifetime_value", "Total revenue attributed to the customer.", "measure"),
        ),
        clarifications=(),
    ),
)

# ------------------------------------------------------------------------ products
_PRODUCTS = DatasetSummary(
    name="products",
    profile=DatasetProfile(
        row_count=1847,
        columns=(
            _col("product_id", T.TEXT, 0, 1847, ("PROD-101", "PROD-422", "PROD-780")),
            _col(
                "product_name",
                T.TEXT,
                0,
                1847,
                ("Wireless Mouse", "USB-C Hub", "4K Monitor"),
            ),
            _col(
                "category", T.TEXT, 0, 12, ("Electronics", "Accessories", "Furniture")
            ),
            _col(
                "list_price",
                T.DECIMAL,
                0,
                310,
                (29.99, 59.95, 499.0),
                minimum=0.99,
                maximum=2499.99,
                quantiles=(19.99, 59.95, 149.99),
            ),
            _col(
                "weight_kg",
                T.DECIMAL,
                72,
                420,
                (0.12, 1.5, 8.2),
                minimum=0.01,
                maximum=45.0,
                quantiles=(0.3, 1.2, 4.5),
            ),
        ),
        encoding="utf-8",
    ),
    catalog=CatalogEntry(
        table_description="Product catalog with pricing and physical attributes.",
        columns=_describe(
            ("product_id", "Unique product SKU.", "identifier"),
            ("product_name", "Display name of the product.", "text"),
            ("category", "Product category.", "category"),
            ("list_price", "Current list price (USD).", "measure"),
            ("weight_kg", "Shipping weight (kg).", "measure"),
        ),
        clarifications=(),
    ),
)


def seed() -> list[DatasetSummary]:
    """The datasets a fresh fixture workspace starts with."""
    return [_SALES, _CUSTOMERS, _PRODUCTS]


def uploaded_transactions() -> DatasetSummary:
    """The dataset produced by the demo upload — exercises mixed/nested/clarify.

    `amount` is profiled as a decimal but a handful of rows carry a currency
    prefix (widened to text-ish facts), and `merchant` triggers a catalog
    clarification about normalization — the AskQuestion primitive on ingest.
    """
    return DatasetSummary(
        name="transactions",
        profile=DatasetProfile(
            row_count=87340,
            columns=(
                _col("txn_id", T.TEXT, 0, 87340, ("TXN-0001", "TXN-0002", "TXN-0003")),
                _col(
                    "txn_ts",
                    T.DATETIME,
                    0,
                    86110,
                    ("2024-10-01 09:14", "2024-10-01 09:22"),
                ),
                _col("account_id", T.TEXT, 0, 9042, ("ACC-2001", "ACC-2002")),
                _col(
                    "amount",
                    T.TEXT,
                    18,
                    41320,
                    ("42.10", "199.00", "$7.49"),
                    is_mixed=True,
                    dominant=T.DECIMAL,
                    off_type=("$7.49", "USD 12.00"),
                ),
                _col("merchant", T.TEXT, 210, 1204, ("Amazon", "AMZN", "Shell")),
            ),
            encoding="utf-8",
            synthesized_headers=False,
            had_duplicate_columns=False,
        ),
        catalog=CatalogEntry(
            table_description="Card transactions, Q4 2024. Auto-catalogued on ingest.",
            columns=_describe(
                ("txn_id", "Unique transaction identifier.", "identifier"),
                ("txn_ts", "Transaction timestamp.", "timestamp"),
                ("account_id", "References an account.", "identifier"),
                (
                    "amount",
                    "Transaction amount; some rows carry a currency prefix.",
                    "measure",
                ),
                ("merchant", "Merchant name; values look unnormalized.", "category"),
            ),
            clarifications=(
                Clarification(
                    question=(
                        "Some merchant values look like the same merchant spelled "
                        "differently (e.g. 'Amazon' vs 'AMZN'). Normalize them?"
                    ),
                    options=("Normalize to a canonical name", "Keep values as-is"),
                    column="merchant",
                ),
            ),
        ),
    )
