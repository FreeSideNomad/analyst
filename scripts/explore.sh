#!/bin/sh
# Exploratory-testing harness: boot the app, tail logs for errors live, and
# summarize defects on exit.
#
#   MODE=mock sh scripts/explore.sh   # mocked data (ANALYST_FIXTURES=1) — seeded workspace
#   MODE=real sh scripts/explore.sh   # real DuckDB store (empty until you upload)
#   uv run python scripts/summarize_defects.py .explore   # re-summarize last session
#
# While it runs: click around http://localhost:5173. API/web log lines stream
# here, error lines highlighted. Ctrl-C stops everything and writes
# .explore/defects.md (also printed to the terminal).
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOGDIR="$ROOT/.explore"
MODE="${MODE:-mock}"
API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-5173}"

mkdir -p "$LOGDIR"
: > "$LOGDIR/api.log"
: > "$LOGDIR/web.log"
printf '%s\n' "$MODE" > "$LOGDIR/mode"

# Per-mode server environment.
#   mock — in-memory fixtures (seeded workspace), no auth, no live model.
#   real — real DuckDB store, no auth, no live cataloguing (fast).
#   mvp  — the full MVP: real store + auth (dev-login) + LIVE agent cataloguing.
API_ENV="ANALYST_FIXTURES=0"
if [ "$MODE" = "mock" ]; then
    API_ENV="ANALYST_FIXTURES=1"
elif [ "$MODE" = "mvp" ]; then
    API_ENV="ANALYST_FIXTURES=0 ANALYST_DEV_LOGIN=1 ANALYST_CATALOG=live \
ANALYST_INSECURE_COOKIES=1 ANALYST_SESSION_SECRET=${ANALYST_SESSION_SECRET:-local-explore-secret}"
fi

cleanup() {
    trap - INT TERM EXIT
    echo ""
    echo "── stopping servers ──────────────────────────────────────────"
    [ -n "${TAIL_PID:-}" ] && kill "$TAIL_PID" 2>/dev/null || true
    [ -n "${API_PID:-}" ] && kill "$API_PID" 2>/dev/null || true
    [ -n "${WEB_PID:-}" ] && kill "$WEB_PID" 2>/dev/null || true
    # vite spawns children; sweep anything still holding our log files
    pkill -f "vite.*--port $WEB_PORT" 2>/dev/null || true
    sleep 1
    uv run python "$ROOT/scripts/summarize_defects.py" "$LOGDIR"
}
trap cleanup INT TERM EXIT

echo "── analyst exploratory session ($MODE) ───────────────────────"
env $API_ENV uv run uvicorn analyst.api.app:app \
    --port "$API_PORT" --log-level info >>"$LOGDIR/api.log" 2>&1 &
API_PID=$!

(cd "$ROOT/frontend" && ANALYST_API="http://127.0.0.1:$API_PORT" \
    bun run dev -- --port "$WEB_PORT" --strictPort >>"$LOGDIR/web.log" 2>&1) &
WEB_PID=$!

# Wait for the API
tries=0
until curl -sf "http://localhost:$API_PORT/api/health" >/dev/null 2>&1; do
    tries=$((tries + 1))
    [ "$tries" -gt 100 ] && { echo "API failed to start — see $LOGDIR/api.log"; exit 1; }
    sleep 0.2
done

echo ""
echo "  app:  http://localhost:$WEB_PORT"
echo "  api:  http://localhost:$API_PORT/api/health  (mode: '"$MODE"')"
echo "  logs: $LOGDIR/{api,web}.log"
echo ""
echo "  Explore away. Error lines are flagged below as they happen."
echo "  Ctrl-C to stop and get the defect summary."
echo "──────────────────────────────────────────────────────────────"

command -v open >/dev/null 2>&1 && [ "${AUTO_OPEN:-1}" = "1" ] && \
    open "http://localhost:$WEB_PORT" || true

# Live tail with source labels; highlight suspicious lines.
tail -f "$LOGDIR/api.log" "$LOGDIR/web.log" | awk '
    /^==> .*api\.log/ { src = "api"; next }
    /^==> .*web\.log/ { src = "web"; next }
    /^$/ { next }
    {
        line = sprintf("[%s] %s", src, $0)
        if ($0 ~ /Traceback|ERROR|error|Error| 500 | 502 | 503 |Unhandled|failed|EADDRINUSE/)
            printf "\033[31m%s\033[0m\n", line
        else
            print line
    }
' &
TAIL_PID=$!

wait "$API_PID"
