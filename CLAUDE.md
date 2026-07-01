# analyst — project instructions

## Acceptance Tests

This project uses the DAE/ATDD acceptance pipeline. Executable acceptance
tests are **generated** from the human-authored spec — never written by hand.

### Pipeline: parse → generate → run

```
features/NNN-slug/spec.md                 # human source (standard Gherkin)
  │  dae_gherkin.py  (portable parser, shipped — not ours)
  ▼
features/NNN-slug/.build/spec.json        # fixed JSON IR
  │  acceptance/generator.py              # OUR generator (reads IR only)
  ▼
features/NNN-slug/.build/generated/       # runnable pytest files
  │  uv run pytest
  ▼
  pass/fail board
```

Run the whole pipeline with:

```sh
./run-acceptance-tests.sh            # add pytest args, e.g. -v, after
```

### The two halves

- **Portable front end (shipped, do not build):** `dae_gherkin.py` parses
  `spec.md` into the fixed JSON IR at `.build/spec.json`.
- **Project-specific back end (committed source, under `acceptance/`):**
  - `acceptance/generator.py` — reads **only** `.build/spec.json` and emits
    pytest files into `.build/generated/`. One test per scenario; Scenario
    Outlines expand to one parameterised test per Examples row; background
    steps are prepended to every scenario. Deterministic for a fixed IR.
  - `acceptance/handlers.py` — a regex step registry binding each step's exact
    text to the real system through the in-process seam
    `IngestionService(DatasetStore(base_dir=...)).ingest(<csv path>)`. A
    `ScenarioContext` flows Given→When→Then; Given steps build CSV fixtures in
    a pytest `tmp_path`; state is fresh per scenario by construction.

### Rules

- **Never** modify `spec.md` to make tests pass — it is the source of truth.
- **Never** hand-edit files under `.build/generated/` — regenerate instead.
  `.build/` is gitignored; `acceptance/` and `run-acceptance-tests.sh` are
  committed.
- The generator reads the IR only; it never re-parses `spec.md`.
- Generated tests fail on an unsupported step, a missing example value, or a
  failed assertion. Failures report the source `spec.md` and the failing
  scenario name.
- Unimplemented steps fail **explicitly** with `NOT YET IMPLEMENTED: <step>` —
  never skipped or xfail'd. A red board is intended: it drives the next slice.
- Always run Python via `uv run` (see `pyproject.toml`).

### Current state (Slice A — walking skeleton)

Fully bound and **passing**: `A clean CSV becomes a profiled, queryable
dataset`. Every other scenario is generated as an explicit failing test that
documents the desired behavior, driving Slices B–F. As each slice lands, add
its step bindings to `acceptance/handlers.py` and re-run the pipeline.
