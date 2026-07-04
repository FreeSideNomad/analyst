#!/bin/sh
# Start + seed the live federation test databases (feature 005).
#   Postgres  → Pagila (auto-seeded via docker-entrypoint-initdb.d)
#   SQL Server→ Northwind (instnwnd.sql via sqlcmd, idempotent)
#   DB2       → SAMPLE (db2sampl, idempotent; slow — amd64-only image)
# Seed SQL is downloaded once and cached in tests/.dbs_seed/ (gitignored).
# Details/caveats: features/005-db-federation/runbook.md
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SEED="$ROOT/tests/.dbs_seed"
COMPOSE="docker compose -f $ROOT/docker-compose.dbs.yml"

PAGILA_BASE="https://raw.githubusercontent.com/devrimgunduz/pagila/master"
NORTHWIND_URL="https://raw.githubusercontent.com/microsoft/sql-server-samples/master/samples/databases/northwind-pubs/instnwnd.sql"

fetch() { # fetch <url> <dest>
    [ -s "$2" ] && return 0
    echo "-- downloading $(basename "$2")"
    mkdir -p "$(dirname "$2")"
    curl -fsSL "$1" -o "$2"
}

fetch "$PAGILA_BASE/pagila-schema.sql" "$SEED/postgres/01-pagila-schema.sql"
fetch "$PAGILA_BASE/pagila-data.sql" "$SEED/postgres/02-pagila-data.sql"
fetch "$NORTHWIND_URL" "$SEED/mssql/instnwnd.sql"

$COMPOSE up -d

echo "-- waiting for postgres (pagila seeds on first boot)"
i=0
until docker exec analyst-dbs-postgres pg_isready -U postgres -d pagila >/dev/null 2>&1; do
    i=$((i + 1)); [ $i -gt 60 ] && { echo "postgres did not come up"; exit 1; }
    sleep 2
done
# first boot keeps seeding after pg_isready; wait for a pagila table
i=0
until docker exec analyst-dbs-postgres psql -U postgres -d pagila -tAc \
    "SELECT COUNT(*) FROM actor" >/dev/null 2>&1; do
    i=$((i + 1)); [ $i -gt 90 ] && { echo "pagila did not seed"; exit 1; }
    sleep 2
done
echo "   pagila ready ($(docker exec analyst-dbs-postgres psql -U postgres -d pagila -tAc 'SELECT COUNT(*) FROM film') films)"

echo "-- waiting for SQL Server (amd64 emulation on Apple silicon: slow)"
SQLCMD="/opt/mssql-tools18/bin/sqlcmd -C"
docker exec analyst-dbs-mssql sh -c "test -x /opt/mssql-tools18/bin/sqlcmd" 2>/dev/null \
    || SQLCMD="/opt/mssql-tools/bin/sqlcmd"
i=0
until docker exec analyst-dbs-mssql $SQLCMD -S localhost -U sa -P 'Analyst!Passw0rd' -Q "SELECT 1" >/dev/null 2>&1; do
    i=$((i + 1)); [ $i -gt 120 ] && { echo "WARN: SQL Server did not come up (see runbook)"; break; }
    sleep 5
done
if docker exec analyst-dbs-mssql $SQLCMD -S localhost -U sa -P 'Analyst!Passw0rd' -Q "SELECT 1" >/dev/null 2>&1; then
    if ! docker exec analyst-dbs-mssql $SQLCMD -S localhost -U sa -P 'Analyst!Passw0rd' -d Northwind -Q "SELECT COUNT(*) FROM Orders" >/dev/null 2>&1; then
        echo "-- seeding Northwind"
        # instnwnd.sql creates objects only — create the database first.
        docker exec analyst-dbs-mssql $SQLCMD -S localhost -U sa -P 'Analyst!Passw0rd' \
            -Q "IF DB_ID('Northwind') IS NULL CREATE DATABASE Northwind" >/dev/null
        docker exec analyst-dbs-mssql $SQLCMD -S localhost -U sa -P 'Analyst!Passw0rd' \
            -d Northwind -i /seed/instnwnd.sql >/dev/null
    fi
    ORDERS=$(docker exec analyst-dbs-mssql $SQLCMD -S localhost -U sa -P 'Analyst!Passw0rd' \
        -d Northwind -h -1 -Q "SET NOCOUNT ON; SELECT COUNT(*) FROM Orders" | tr -d '[:space:]')
    echo "   Northwind ready ($ORDERS orders)"
fi

echo "-- DB2: booting in the background (10+ min under emulation, if at all)."
echo "   When up, create SAMPLE with:"
echo "   docker exec analyst-dbs-db2 su - db2inst1 -c db2sampl"
echo
echo "Run the live tests:  uv run pytest tests/live -m live -v"
