"""Seed a relational database with the curated (decoded) Berka tables —
feature 019's 'the user's data lives in a database' arrival path.

    uv run python scripts/seed_berka_db.py sqlite  <path.db>
    uv run python scripts/seed_berka_db.py postgres <conninfo>

Reads the engine's built berka database (downloading/building on demand
into ANALYST_ML_CACHE) and copies each table via DuckDB's sqlite/postgres
extensions — no extra drivers. Table names are plain (loan, account, …);
connected through analyst they become `<connection>.<table>` records, so
the workspace aliases match the upload path (berka_loan, …) and the
equivalence gate compares like for like.
"""

from __future__ import annotations

import sys

import duckdb

from analyst.engine.relgraph.builddb import db_path
from analyst.engine.relgraph.pipeline import ensure_data
from analyst.engine.relgraph.registry import get_spec


def seed(engine: str, target: str) -> list[str]:
    ensure_data("berka")
    spec = get_spec("berka")
    con = duckdb.connect()
    messages = []
    try:
        con.execute(f"ATTACH '{db_path('berka')}' AS src (READ_ONLY)")
        if engine == "sqlite":
            con.execute(f"ATTACH '{target}' AS dst (TYPE sqlite)")
        elif engine == "postgres":
            con.execute(f"ATTACH '{target}' AS dst (TYPE postgres)")
        else:
            raise SystemExit(f"unknown engine '{engine}' (sqlite|postgres)")
        for tname in spec.tables:
            con.execute(f'DROP TABLE IF EXISTS dst."{tname}"')
            con.execute(f'CREATE TABLE dst."{tname}" AS SELECT * FROM src."{tname}"')
            count = con.execute(f'SELECT COUNT(*) FROM dst."{tname}"').fetchone()
            messages.append(f"{tname}: {count[0] if count else 0} rows")
    finally:
        con.close()
    return messages


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    for line in seed(sys.argv[1], sys.argv[2]):
        print(line)
