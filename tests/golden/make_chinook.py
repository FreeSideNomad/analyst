"""Generate tests/golden/chinook.sqlite — the bundled sample database.

A small, referentially-intact subset of the MIT-licensed Chinook database
(github.com/lerocha/chinook-database): full schema with declared PK/FK
constraints, reduced rows. The output is committed so unit/acceptance/e2e
runs are deterministic and offline; this script documents provenance and
regenerates the fixture (download is cached in tests/.golden_cache).

Usage: uv run python tests/golden/make_chinook.py
"""

from __future__ import annotations

import sqlite3
import urllib.request
from pathlib import Path

CHINOOK_URL = (
    "https://github.com/lerocha/chinook-database/releases/download/"
    "v1.4.5/Chinook_Sqlite.sqlite"
)
ROOT = Path(__file__).resolve().parent.parent.parent
CACHE = ROOT / "tests" / ".golden_cache" / "chinook_full.sqlite"
OUT = ROOT / "tests" / "golden" / "chinook.sqlite"

# Referential closure, smallest first: filters applied in dependency order.
FILTERS = {
    "Artist": "ArtistId <= 30",
    "Album": "ArtistId <= 30",
    "Genre": "1=1",
    "MediaType": "1=1",
    "Track": "AlbumId IN (SELECT AlbumId FROM Album WHERE ArtistId <= 30)",
    "Employee": "1=1",
    "Customer": "CustomerId <= 20",
    "Invoice": "CustomerId <= 20 AND InvoiceId <= 120",
    "InvoiceLine": (
        "InvoiceId IN (SELECT InvoiceId FROM Invoice"
        "              WHERE CustomerId <= 20 AND InvoiceId <= 120)"
        " AND TrackId IN (SELECT TrackId FROM Track WHERE AlbumId IN"
        "                 (SELECT AlbumId FROM Album WHERE ArtistId <= 30))"
    ),
    "Playlist": "PlaylistId <= 5",
    "PlaylistTrack": (
        "PlaylistId <= 5 AND TrackId IN (SELECT TrackId FROM Track"
        " WHERE AlbumId IN (SELECT AlbumId FROM Album WHERE ArtistId <= 30))"
    ),
}


def main() -> None:
    if not CACHE.exists():
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        print(f"downloading {CHINOOK_URL}")
        urllib.request.urlretrieve(CHINOOK_URL, CACHE)  # noqa: S310

    OUT.unlink(missing_ok=True)
    src = sqlite3.connect(CACHE)
    dst = sqlite3.connect(OUT)
    dst.execute("PRAGMA foreign_keys = OFF")

    # Recreate the full declared schema (PKs + FKs) verbatim.
    for (ddl,) in src.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND sql IS NOT NULL"
    ):
        dst.execute(ddl)

    for table, where in FILTERS.items():
        rows = src.execute(f"SELECT * FROM {table} WHERE {where}").fetchall()  # noqa: S608
        if rows:
            marks = ", ".join("?" for _ in rows[0])
            dst.executemany(
                f"INSERT INTO {table} VALUES ({marks})",  # noqa: S608
                rows,
            )
        print(f"{table}: {len(rows)} rows")

    dst.commit()
    violations = dst.execute("PRAGMA foreign_key_check").fetchall()
    assert not violations, f"FK violations in subset: {violations[:5]}"
    dst.execute("VACUUM")
    dst.close()
    src.close()
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
