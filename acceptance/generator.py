"""Generator — turn the fixed JSON IR into runnable pytest files.

Reads ONLY the IR (``.build/spec.json`` produced by the portable
``dae_gherkin.py`` parser); it never re-parses ``spec.md``. For a fixed IR
the output is deterministic.

Emitted, per feature, into ``<output_dir>``:
- ``conftest.py``      — makes the committed ``acceptance`` package importable.
- ``test_acceptance.py`` — one test function per scenario; Scenario Outlines
  are expanded to one parameterised test function per Examples row.
  Background steps (if any) are prepended to every scenario.

Each generated test replays its steps through
``acceptance.handlers.run_step``, which binds step text to the real system
or fails explicitly on an unimplemented step.

Usage:
    generator.py <spec.json> <output_dir> [<spec.md>]
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path


# --------------------------------------------------------------------------- #
# IR helpers
# --------------------------------------------------------------------------- #
def _substitute(text: str, example: dict[str, str]) -> str:
    """Replace ``<param>`` placeholders in a step with example-row values."""
    for key, value in example.items():
        text = text.replace(f"<{key}>", str(value))
    return text


def _slug(text: str) -> str:
    """A safe, deterministic Python-identifier fragment from arbitrary text."""
    slug = re.sub(r"[^0-9a-zA-Z]+", "_", text.strip().lower()).strip("_")
    return slug or "scenario"


def _expand(scenario: dict) -> list[list[dict]]:
    """Expand a scenario into one or more concrete (keyword, text) step lists.

    A plain scenario yields a single list. A Scenario Outline yields one list
    per Examples row, with ``<param>`` placeholders substituted.
    """
    examples = scenario.get("examples") or [{}]
    executions: list[list[dict]] = []
    for example in examples:
        steps = [
            {"keyword": s["keyword"], "text": _substitute(s["text"], example)}
            for s in scenario["steps"]
        ]
        executions.append(steps)
    return executions


# --------------------------------------------------------------------------- #
# Code emission
# --------------------------------------------------------------------------- #
_CONFTEST = '''\
"""Generated — DO NOT EDIT. Regenerate via acceptance/generator.py.

Puts the repo root on sys.path so the committed ``acceptance`` package
(handlers + registry) is importable when pytest runs the generated tests.
"""
import sys
from pathlib import Path


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file():
            return parent
    return here.parents[-1]


sys.path.insert(0, str(_repo_root()))
'''


def _emit_test_function(name: str, scenario_name: str, steps: list[dict]) -> str:
    lines = [
        f"def {name}(tmp_path):",
        "    ctx = ScenarioContext(tmp_path=tmp_path)",
        f"    ctx.scenario = {scenario_name!r}",
        "    ctx.spec = SPEC_MD",
        "    steps = [",
    ]
    for s in steps:
        lines.append(f"        ({s['keyword']!r}, {s['text']!r}),")
    lines.extend(
        [
            "    ]",
            "    for keyword, text in steps:",
            "        run_step(ctx, keyword, text)",
        ]
    )
    return "\n".join(lines)


def generate(spec_json: Path, output_dir: Path, spec_md: Path) -> int:
    ir = json.loads(spec_json.read_text(encoding="utf-8"))
    background = ir.get("background") or []

    # Clean + recreate the output dir so stale tests never linger.
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    (output_dir / "conftest.py").write_text(_CONFTEST, encoding="utf-8")

    blocks: list[str] = [
        '"""Generated acceptance tests — DO NOT EDIT.',
        "",
        f"Feature: {ir.get('name', '')}",
        f"Source:  {spec_md}",
        "Regenerate via acceptance/generator.py (reads .build/spec.json only).",
        '"""',
        "from acceptance.handlers import ScenarioContext, run_step",
        "",
        f"SPEC_MD = {str(spec_md)!r}",
        "",
    ]

    used: set[str] = set()
    scenario_count = 0
    test_count = 0
    for scenario in ir["scenarios"]:
        scenario_name = scenario["name"]
        scenario_count += 1
        executions = _expand(scenario)
        multi = len(executions) > 1
        for row_index, concrete_steps in enumerate(executions):
            steps = background + concrete_steps
            name = f"test_{test_count:02d}_{_slug(scenario_name)}"
            if multi:
                # Disambiguate + trace back to the Examples row values.
                example = (scenario.get("examples") or [{}])[row_index]
                suffix = "_".join(_slug(str(v)) for v in example.values())
                name = f"{name}__{suffix}" if suffix else f"{name}__{row_index}"
            while name in used:  # guarantee uniqueness deterministically
                name = f"{name}_x"
            used.add(name)
            blocks.append(_emit_test_function(name, scenario_name, steps))
            blocks.append("")
            blocks.append("")
            test_count += 1

    (output_dir / "test_acceptance.py").write_text(
        "\n".join(blocks).rstrip() + "\n", encoding="utf-8"
    )

    print(
        f"generated {test_count} test(s) from {scenario_count} scenario(s) "
        f"-> {output_dir}"
    )
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(
            "usage: generator.py <spec.json> <output_dir> [<spec.md>]",
            file=sys.stderr,
        )
        return 3
    spec_json = Path(argv[1])
    output_dir = Path(argv[2])
    if len(argv) >= 4:
        spec_md = Path(argv[3])
    else:
        # Default: spec.md is the feature dir's source, two levels above .build.
        spec_md = spec_json.parent.parent / "spec.md"
    return generate(spec_json, output_dir, spec_md)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
