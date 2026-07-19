"""Label fidelity: every UI control the tutorial names must exist in the
product. Guards the prose against silent rot when a control is renamed
(it happened: 'Author relational task' became 'Author from question').

Bold spans in tutorial/pages/*.md that look like UI labels (Capitalized,
short) must appear verbatim somewhere in the frontend or backend source.
Anything intentionally not a control lives in ALLOWED_EMPHASIS.

    python3 tutorial/check_labels.py     # stdlib only; used by CI
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES = ROOT / "tutorial" / "pages"
SOURCE_TREES = [ROOT / "frontend" / "src", ROOT / "src" / "analyst"]

# Bold spans that are emphasis or domain terms, not UI controls.
ALLOWED_EMPHASIS = {
    "analyst",
    "All you need is Docker and a browser.",
    "Part 1 — no AI key needed.",
    "Part 2 — bring an AI key.",
    "without the data moving",
    "held back",
    "hidden from the model",
    "across the two connections",
    "already reconnected",
    "real banking data",
    "An Anthropic API key",
    "A Claude subscription token",
    "What the AI can and cannot see.",
    "What you can do now:",
    "ML edition",
    "deliberately scrambled outcomes",
    "decisions laid out for your approval",
    "as of the day each loan was granted",
    "no AI key",
    "bold UI label",
    "SalePrice",  # a data column the user picks, not a control
    "CRM",
    "billing",
}

LABEL_SHAPE = re.compile(r"^[A-Z][\w &()'-]*(\s[\w&()'-]+){0,5}$")


def main() -> int:
    haystack = "\n".join(
        p.read_text(errors="ignore")
        for tree in SOURCE_TREES
        for p in tree.rglob("*")
        if p.suffix in (".tsx", ".ts", ".py") and p.is_file()
    )
    failures = []
    for page in sorted(PAGES.glob("*.md")):
        for span in re.findall(r"\*\*([^*]+)\*\*", page.read_text()):
            span = re.sub(r"\s+", " ", span)  # bold spans wrap across lines
            text = span.strip().rstrip(".")
            if text in ALLOWED_EMPHASIS or span.strip() in ALLOWED_EMPHASIS:
                continue
            if not LABEL_SHAPE.match(text):
                continue
            if "[" in text or "http" in text:
                continue
            if text not in haystack:
                failures.append(
                    f"{page.name}: **{span.strip()}** not found in the UI/product source"
                )
    if failures:
        print("Tutorial references UI labels that do not exist:\n")
        print("\n".join(f"  - {f}" for f in failures))
        print(
            "\nEither the control was renamed (fix the tutorial) or the span "
            "is emphasis (add it to ALLOWED_EMPHASIS in tutorial/check_labels.py)."
        )
        return 1
    print("tutorial label fidelity: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
