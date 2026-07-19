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

### Current state (features 001–019 shipped)

**All 18 boards are fully bound and green — 276 scenarios** (in-process +
Playwright browser e2e). Each feature folder's `.handlers` file names its
binding module: `acceptance/handlers.py` (001), `ctxNNN.py` (in-process
seams), `e2e_NNN.py` (modules that also boot the fixtures app + Chromium;
skipped with `E2E=0`).

Conventions that keep the boards honest:

- **Agent turns replay cassettes** in `tests/cassettes/`, recorded once live
  by `scripts/record_*_cassette.py`. Recording scripts must mirror the
  bindings byte-for-byte (same fixtures, same workspace) or replay keys miss.
- **Commit the implementation BEFORE running mutation gates** — gates revert
  with `git checkout`, which destroys uncommitted work.
- Never `git commit -q` — it hides pre-commit failures and drops commits
  silently.
- ruff's autofix strips imports that only later-appended code uses; hoist
  imports when growing a handler module incrementally.
- Playwright `get_by_label` matches substrings: keep aria-labels
  prefix-free of each other or bind with `exact=True`.
