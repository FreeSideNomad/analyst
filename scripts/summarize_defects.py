"""Summarize an exploratory session's logs into a defect report.

Reads .explore/{api,web}.log, classifies what happened, and writes
.explore/defects.md (also printed to stdout).

Defects   — server tracebacks (grouped by exception), HTTP 5xx responses,
            frontend build/dev-server errors.
Notes     — HTTP 4xx responses (often expected: probing unknown datasets),
            warnings.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

ACCESS = re.compile(r'"(?P<method>[A-Z]+) (?P<path>\S+) HTTP/[\d.]+" (?P<code>\d{3})')
WEB_ERROR = re.compile(r"error|failed|EADDRINUSE|Internal server error", re.IGNORECASE)


def _tracebacks(text: str) -> Counter:
    """Group tracebacks by their final exception line."""
    found: Counter = Counter()
    block: list[str] = []
    in_tb = False
    for line in text.splitlines():
        if line.startswith("Traceback ("):
            in_tb, block = True, []
        elif in_tb:
            block.append(line)
            # the exception line: no leading whitespace, "Type: message"
            if line and not line.startswith((" ", "\t")):
                found[line.strip()] += 1
                in_tb = False
    return found


def _requests(text: str) -> tuple[Counter, Counter]:
    """(5xx defects, 4xx notes) as 'CODE METHOD path' counters."""
    server_errors: Counter = Counter()
    client_errors: Counter = Counter()
    for match in ACCESS.finditer(text):
        code = int(match.group("code"))
        key = f"{code} {match.group('method')} {match.group('path')}"
        if code >= 500:
            server_errors[key] += 1
        elif code >= 400:
            client_errors[key] += 1
    return server_errors, client_errors


def _web_errors(text: str) -> Counter:
    found: Counter = Counter()
    for line in text.splitlines():
        stripped = line.strip()
        # skip bun's command echo and vite's startup banner noise
        if not stripped or stripped.startswith(("$", "➜", "VITE")):
            continue
        if WEB_ERROR.search(stripped):
            found[stripped[:160]] += 1
    return found


def main(log_dir: str) -> int:
    logs = Path(log_dir)
    api_text = (
        (logs / "api.log").read_text(errors="replace")
        if (logs / "api.log").exists()
        else ""
    )
    web_text = (
        (logs / "web.log").read_text(errors="replace")
        if (logs / "web.log").exists()
        else ""
    )
    mode = (logs / "mode").read_text().strip() if (logs / "mode").exists() else "?"

    tracebacks = _tracebacks(api_text)
    server_errors, client_errors = _requests(api_text)
    web_errors = _web_errors(web_text)
    total_requests = len(ACCESS.findall(api_text))
    defect_count = (
        sum(tracebacks.values())
        + sum(server_errors.values())
        + sum(web_errors.values())
    )

    lines = [
        "# Exploratory session — defect summary",
        "",
        f"- mode: **{mode} data** · API requests observed: **{total_requests}**",
        f"- defects: **{defect_count}** · notes (4xx): "
        f"**{sum(client_errors.values())}**",
        "",
    ]

    def section(title: str, counter: Counter, empty: str) -> None:
        lines.append(f"## {title}")
        if not counter:
            lines.append(f"- none — {empty}")
        else:
            for item, count in counter.most_common():
                lines.append(f"- `{item}` × {count}")
        lines.append("")

    section("Defects — server tracebacks", tracebacks, "no unhandled exceptions")
    section("Defects — HTTP 5xx", server_errors, "no server errors")
    section("Defects — frontend dev-server errors", web_errors, "web log clean")
    section(
        "Notes — HTTP 4xx (often expected while probing)",
        client_errors,
        "no client errors",
    )
    lines.append(
        "_Browser-console errors aren't captured here — check devtools while "
        "exploring. Raw logs: `.explore/api.log`, `.explore/web.log`._"
    )

    report = "\n".join(lines) + "\n"
    (logs / "defects.md").write_text(report, encoding="utf-8")
    print(report)
    print(f"(written to {logs / 'defects.md'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else ".explore"))
