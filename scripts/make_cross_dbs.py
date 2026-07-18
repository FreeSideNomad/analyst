"""Generate the synthetic cross-database sample kit (feature 017).

    uv run python scripts/make_cross_dbs.py [out_dir]

Two SQLite databases with a key that only makes sense ACROSS them:

  crm.db      customers(customer_id PK, name, segment, region)   3 rows
  billing.db  invoices(invoice_id PK, customer_id, amount, issued) 4 rows

Documented totals (revenue by segment, the canonical cross-DB question):
  enterprise = 150.0   (C1: 100 + 50)
  smb        =  50.0   (C2: 30, C3: 20)

Deterministic by construction — same rows, same order, every run. Synthetic
on purpose: join mechanics need controlled keys, not organic signal.
Connect both files through "Add data → Connect a database → SQLite".
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

CUSTOMERS = [
    ("C1", "Acme Corp", "enterprise", "East"),
    ("C2", "Bolt LLC", "smb", "West"),
    ("C3", "Cyan Ltd", "smb", "East"),
]
INVOICES = [
    ("I1", "C1", 100.0, "2026-05-01"),
    ("I2", "C1", 50.0, "2026-05-15"),
    ("I3", "C2", 30.0, "2026-05-20"),
    ("I4", "C3", 20.0, "2026-06-02"),
]


def make(out_dir: str | Path) -> tuple[Path, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    crm = out / "crm.db"
    billing = out / "billing.db"
    for path in (crm, billing):
        path.unlink(missing_ok=True)

    con = sqlite3.connect(crm)
    con.execute(
        "CREATE TABLE customers (customer_id TEXT PRIMARY KEY, name TEXT, "
        "segment TEXT, region TEXT)"
    )
    con.executemany("INSERT INTO customers VALUES (?,?,?,?)", CUSTOMERS)
    con.commit()
    con.close()

    con = sqlite3.connect(billing)
    con.execute(
        "CREATE TABLE invoices (invoice_id TEXT PRIMARY KEY, customer_id TEXT, "
        "amount REAL, issued TEXT)"
    )
    con.executemany("INSERT INTO invoices VALUES (?,?,?,?)", INVOICES)
    con.commit()
    con.close()
    return crm, billing


if __name__ == "__main__":
    crm, billing = make(sys.argv[1] if len(sys.argv) > 1 else "samples/verify/dbs")
    print(f"wrote {crm} and {billing} — enterprise 150.0, smb 50.0")
