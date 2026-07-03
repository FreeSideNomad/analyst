#!/bin/sh
# DAE acceptance pipeline: parse -> generate -> run, per feature.
#
#   spec.md --(dae_gherkin.py)--> .build/spec.json --(generator.py)-->
#   .build/generated/  --(uv run pytest)--> pass/fail board
#
# Feature 001 binds steps in-process (acceptance/handlers.py).
# Feature 002 binds steps to HTTP + Playwright (acceptance/e2e_handlers.py) —
#   it boots the fixtures API + the built frontend and drives Chromium
#   (needs: bun, `uv run playwright install chromium`).
#
# Usage:
#   ./run-acceptance-tests.sh            # both features
#   E2E=0 ./run-acceptance-tests.sh      # feature 001 only (skip browser e2e)
#   ./run-acceptance-tests.sh -k delete  # extra args forwarded to pytest
#
# The parser + IR are portable (shipped). The generator + step handlers under
# acceptance/ are this project's committed source. Never hand-edit the files
# under .build/generated/ — always regenerate.
set -eu

ROOT="$(cd "$(dirname "$0")" && pwd)"

# Gherkin parser: the MIT-licensed DAE parser, vendored for reproducibility
# (CI has no plugin cache). Override with DAE=<dir> to use a plugin copy.
DAE="${DAE:-$ROOT/acceptance/vendor}"

run_feature() {
    FEATURE="$ROOT/features/$1"
    HANDLERS="$2"
    shift 2
    BUILD="$FEATURE/.build"
    GENERATED="$BUILD/generated"
    mkdir -p "$BUILD"
    uv run python "$DAE/dae_gherkin.py" "$FEATURE/spec.md" "$BUILD/spec.json"
    uv run python "$ROOT/acceptance/generator.py" \
        "$BUILD/spec.json" "$GENERATED" "$FEATURE/spec.md" "$HANDLERS"
    uv run pytest "$GENERATED" "$@"
}

run_feature 001-file-ingestion-and-profiling acceptance.handlers "$@"

if [ "${E2E:-1}" != "0" ]; then
    run_feature 002-api-and-frontend acceptance.e2e_handlers "$@"
fi
