"""Copy every table of a SQLite file into a Postgres database — used by
the tutorial-images workflow to bake the CRM/billing pair into pre-seeded
images.

    uv run python scripts/seed_sqlite_to_postgres.py <file.db> <conninfo>
"""

from __future__ import annotations

import sys

import duckdb


def seed(sqlite_path: str, conninfo: str) -> list[str]:
    con = duckdb.connect()
    messages = []
    try:
        con.execute(f"ATTACH '{sqlite_path}' AS src (TYPE sqlite, READ_ONLY)")
        con.execute(f"ATTACH '{conninfo}' AS dst (TYPE postgres)")
        tables = [
            r[0]
            for r in con.execute(
                "SELECT table_name FROM duckdb_tables() WHERE database_name='src'"
            ).fetchall()
        ]
        for tname in tables:
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
