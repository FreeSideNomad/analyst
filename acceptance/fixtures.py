"""Shared fixture data for cataloguing scenarios (Slice D).

Kept in one place so the live cassette-recorders and the acceptance handlers
build byte-identical inputs — the record/replay key derives from the profiled
payload, so the CSV must match exactly.
"""

from pathlib import Path

CASSETTE_DIR = Path(__file__).parent.parent / "tests" / "cassettes"
ORDERS_CASSETTE = CASSETTE_DIR / "ingest_orders.json"
AMBIGUOUS_CASSETTE = CASSETTE_DIR / "ingest_ambiguous.json"

# A clean, unambiguous CSV describing customer orders (AC-4).
# Explicit column names (amount_usd, customer_name) so nothing is ambiguous —
# the model should produce descriptions + roles with no clarifying questions.
ORDERS_CSV = (
    "order_id,customer_name,amount_usd,order_placed_at\n"
    "1,alice,10.50,2024-01-15 09:30:00\n"
    "2,bob,20.00,2024-02-20 14:00:00\n"
    "3,carol,30.25,2024-03-05 22:15:00\n"
)

# A dataset with an opaque column the model can't confidently describe (AC-22).
AMBIGUOUS_CSV = "id,x7\n1,QZ\n2,ZP\n3,QP\n4,ZZ\n"
