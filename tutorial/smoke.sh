#!/bin/sh
# Tutorial smoke — behaves exactly like the docker-only user the tutorial
# is written for: everything comes from the LIVE Pages site and the
# PUBLISHED ghcr images. The tutorial requires a Claude token, so the
# smoke does too: set CLAUDE_CODE_OAUTH_TOKEN (or ANTHROPIC_API_KEY) in
# the environment, exactly as the tutorial tells its reader to.
#
#   CLAUDE_CODE_OAUTH_TOKEN=... sh tutorial/smoke.sh   # against the live site
#   PAGES=http://localhost:4000 sh ...                 # against a local preview
#
# Exits non-zero on the first broken link, unhealthy container, failed
# upload, missing relationship, failed connection, or failed training.
set -eu

if [ -z "${CLAUDE_CODE_OAUTH_TOKEN:-}" ] && [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  echo "CLAUDE_CODE_OAUTH_TOKEN (or ANTHROPIC_API_KEY) must be set — the tutorial requires it, so the smoke does too." >&2
  exit 1
fi

PAGES="${PAGES:-https://freesidenomad.github.io/analyst/tutorial}"
WORK="$(mktemp -d)"
cd "$WORK"
echo "work dir: $WORK"

say() { printf '\n== %s\n' "$*"; }

say "the compose file downloads from Pages"
curl -fsSO "$PAGES/docker-compose.yml"
docker compose config -q

say "every sample file the chapters link to downloads"
for f in messy_sales.csv customers.csv purchases.csv company.xlsx \
         messy_orders.csv analyst-tutorial-files.zip; do
  curl -fsSo "$f" "$PAGES/files/$f"
done
ls -l

say "the published stack starts (all profiles)"
docker compose --profile databases --profile ml pull -q
docker compose --profile databases --profile ml up -d

wait_health() {
  url="$1"; name="$2"; deadline=$(( $(date +%s) + 420 ))
  until curl -fsS "$url" >/dev/null 2>&1; do
    [ "$(date +%s)" -gt "$deadline" ] && { echo "$name never became healthy"; exit 1; }
    sleep 3
  done
  echo "$name healthy"
}
wait_health http://localhost:8000/api/health "analyst"
wait_health http://localhost:8001/api/health "analyst-ml"

say "chapter 1: uploads profile and link up"
for f in messy_sales.csv customers.csv purchases.csv company.xlsx messy_orders.csv; do
  curl -fsS -X POST http://localhost:8000/api/datasets/ingest -F "file=@$f" >/dev/null
done
deadline=$(( $(date +%s) + 600 ))
until curl -fsS http://localhost:8000/api/datasets | python3 -c "
import json, sys
data = json.load(sys.stdin)
names = {d['name'] for d in data}
assert {'messy_sales.csv', 'customers.csv', 'purchases.csv'} <= names, names
assert all(d['status'] == 'complete' for d in data), 'still ingesting'
linked = any(
    (d.get('catalog') or {}).get('relationships') for d in data
    if d['name'] == 'purchases.csv'
)
assert linked, 'purchases -> customers link missing'
print('uploads complete; link discovered')
" 2>/dev/null; do
  [ "$(date +%s)" -gt "$deadline" ] && { echo "uploads never completed"; exit 1; }
  sleep 3
done

say "chapter 2: the three seeded databases connect"
for db in berka crm billing; do
  host="$db-db"
  curl -fsS -X POST http://localhost:8000/api/databases/connect \
    -H 'content-type: application/json' \
    -d "{\"name\":\"$db\",\"engine\":\"postgres\",\"host\":\"$host\",\"port\":5432,\"database\":\"$db\",\"user\":\"postgres\",\"password\":\"tutorial\"}" \
    -o /dev/null -w "connect $db: %{http_code}\n" | grep -q 201
done
deadline=$(( $(date +%s) + 300 ))
until curl -fsS http://localhost:8000/api/datasets | python3 -c "
import json, sys
data = json.load(sys.stdin)
berka = [d for d in data if d['name'].startswith('berka.')]
assert len(berka) >= 9, f'only {len(berka)} berka tables'
loan = next(d for d in berka if d['name'] == 'berka.loan')
assert loan['rowCount'] == 682, loan['rowCount']
assert any(d['name'] == 'crm.customers' for d in data)
assert any(d['name'] == 'billing.invoices' for d in data)
print('all three databases catalogued in place')
" 2>/dev/null; do
  [ "$(date +%s)" -gt "$deadline" ] && { echo "connections never catalogued"; exit 1; }
  sleep 5
done

say "chapter 5: the relational bundle trains on the ML app"
curl -fsS -X POST http://localhost:8001/api/models/relational/bundle >/dev/null
deadline=$(( $(date +%s) + 300 ))
until curl -fsS http://localhost:8001/api/datasets | python3 -c "
import json, sys
names = {d['name'] for d in json.load(sys.stdin)}
assert 'berka_loan.csv' in names
" 2>/dev/null; do
  [ "$(date +%s)" -gt "$deadline" ] && { echo "bundle never arrived"; exit 1; }
  sleep 5
done
curl -fsS -X POST http://localhost:8001/api/models/relational/tasks \
  -H 'content-type: application/json' -d '{"task":"loan_default"}' >/dev/null
curl -fsS -X POST --max-time 1200 \
  http://localhost:8001/api/models/relational/tasks/berka-loan-default/train \
  | python3 -c "
import json, sys
task = json.load(sys.stdin)
assert task['status'] == 'trained', task['status']
scores = {t: round(m['test_auroc'], 3) for t, m in task['metrics'].items()}
print('trained:', scores)
assert 0.5 < task['metrics']['graph']['test_auroc'] <= 1
"
curl -fsS http://localhost:8001/api/datasets | python3 -c "
import json, sys
preds = [d for d in json.load(sys.stdin) if 'predictions' in d['name']]
assert preds and preds[0]['rowCount'] == 682, preds
print('predictions dataset present: 682 loans')
"

say "smoke green — the published tutorial stack works end to end"
docker compose --profile databases --profile ml down -v >/dev/null 2>&1 || true
