#!/bin/sh
# DAE acceptance pipeline: parse -> generate -> run, for EVERY feature that
# has a spec.md.
#
#   features/NNN-slug/spec.md --(vendored dae_gherkin.py)--> .build/spec.json
#     --(acceptance/generator.py)--> .build/generated/ --(pytest)--> board
#
# Binding layer per feature: features/NNN-slug/.handlers names the handlers
# module (default: acceptance.handlers, the in-process binding). Browser-bound
# modules (built on acceptance/e2e_base.py) boot the fixtures API + the built
# frontend + Chromium; skip those with E2E=0.
#
# Usage:
#   ./run-acceptance-tests.sh            # all feature boards
#   E2E=0 ./run-acceptance-tests.sh      # skip browser-bound boards
#   ./run-acceptance-tests.sh -k delete  # extra args forwarded to pytest
#   BOARD_FILTER='012|018' ...           # only boards whose folder matches
#   BOARD_EXCLUDE='012|018|019' ...      # every board except these
set -eu

ROOT="$(cd "$(dirname "$0")" && pwd)"

# Gherkin parser: the MIT-licensed DAE parser, vendored for reproducibility
# (CI has no plugin cache). Override with DAE=<dir> to use a plugin copy.
DAE="${DAE:-$ROOT/acceptance/vendor}"

for SPEC in "$ROOT"/features/*/spec.md; do
    [ -f "$SPEC" ] || continue
    FEATURE="$(dirname "$SPEC")"
    NAME="$(basename "$FEATURE")"
    if [ -n "${BOARD_FILTER:-}" ] && ! echo "$NAME" | grep -qE "$BOARD_FILTER"; then
        continue
    fi
    if [ -n "${BOARD_EXCLUDE:-}" ] && echo "$NAME" | grep -qE "$BOARD_EXCLUDE"; then
        continue
    fi
    HANDLERS="acceptance.handlers"
    [ -f "$FEATURE/.handlers" ] && HANDLERS="$(cat "$FEATURE/.handlers")"
    case "$HANDLERS" in
        *e2e*) [ "${E2E:-1}" = "0" ] && {
            echo "-- skipping $(basename "$FEATURE") (E2E=0)"; continue; } ;;
    esac
    BUILD="$FEATURE/.build"
    mkdir -p "$BUILD"
    echo "== $(basename "$FEATURE")  [$HANDLERS]"
    uv run python "$DAE/dae_gherkin.py" "$SPEC" "$BUILD/spec.json"
    uv run python "$ROOT/acceptance/generator.py" \
        "$BUILD/spec.json" "$BUILD/generated" "$SPEC" "$HANDLERS"
    uv run pytest "$BUILD/generated" "$@"
done
