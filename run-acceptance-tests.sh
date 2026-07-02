#!/bin/sh
# DAE acceptance pipeline (feature 001): parse -> generate -> run.
#
#   spec.md --(dae_gherkin.py)--> .build/spec.json --(generator.py)-->
#   .build/generated/  --(uv run pytest)--> pass/fail board
#
# The parser + IR are portable (shipped). The generator + step handlers under
# acceptance/ are this project's committed source. Never hand-edit the files
# under .build/generated/ — always regenerate.
set -eu

ROOT="$(cd "$(dirname "$0")" && pwd)"
FEATURE="$ROOT/features/001-file-ingestion-and-profiling"
BUILD="$FEATURE/.build"
GENERATED="$BUILD/generated"

# Portable parser location (override with DAE=... if the version moves).
DAE="${DAE:-/Users/igormusic/.claude/plugins/cache/disciplined-agentic-engineering/engineer/0.19.0/scripts}"

mkdir -p "$BUILD"

# 1. Parse standard Gherkin (spec.md) into the fixed JSON IR.
uv run python "$DAE/dae_gherkin.py" "$FEATURE/spec.md" "$BUILD/spec.json"

# 2. Generate runnable pytest files from the IR (reads spec.json only).
uv run python "$ROOT/acceptance/generator.py" \
    "$BUILD/spec.json" "$GENERATED" "$FEATURE/spec.md"

# 3. Run the generated acceptance tests.
uv run pytest "$GENERATED" "$@"
