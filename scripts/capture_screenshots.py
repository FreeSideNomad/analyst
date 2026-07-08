"""Capture the user-manual screenshots (docs/site/img/) from the fixtures app.

    uv run python scripts/capture_screenshots.py

Boots ONE uvicorn process (fixtures API + built frontend via ANALYST_WEB_DIST)
and drives the real UI with Playwright. Requires a fresh `frontend/dist`
(`cd frontend && bun run build`) and Playwright's Chromium.

State assumptions are ASSERTED, not clicked into being — notably, the latest
answer's trust trail arrives EXPANDED by default (pinned by the feature-003
board; the 2026-07-08 fix investigation traced a phantom "collapse bug" to a
script that clicked the already-open trail closed).
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "docs" / "site" / "img"
OUT.mkdir(parents=True, exist_ok=True)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main() -> None:
    port = _free_port()
    url = f"http://127.0.0.1:{port}"
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "analyst.api.app:app",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=REPO,
        env={
            **os.environ,
            "ANALYST_FIXTURES": "1",
            "ANALYST_WEB_DIST": str(REPO / "frontend" / "dist"),
        },
    )
    try:
        for _ in range(100):
            try:
                if httpx.get(f"{url}/api/health", timeout=1).status_code == 200:
                    break
            except Exception:  # noqa: BLE001 - booting
                time.sleep(0.2)
        else:
            raise SystemExit("app did not come up")
        _capture(url)
    finally:
        proc.terminate()
        proc.wait(timeout=10)
    print("done ->", OUT)


def _capture(url: str) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(
            viewport={"width": 1440, "height": 900}, device_scale_factor=2
        )

        def shot(name: str, pause: float = 0.6) -> None:
            time.sleep(pause)
            page.screenshot(path=str(OUT / f"{name}.png"))
            print("captured", name)

        # Catalog + table detail (the app opens here; select sales)
        page.goto(url)
        page.get_by_text("Catalog", exact=True).first.wait_for()
        page.get_by_role("button", name="Open table sales").first.click()
        shot("catalog")

        # Query home — suggestion chips, empty thread
        page.get_by_role("button", name="Query").click()
        page.get_by_placeholder("Ask across all tables").wait_for()
        shot("query-home")

        # Ask -> clarification
        box = page.get_by_placeholder("Ask across all tables")
        box.fill("What is the revenue by region?")
        box.press("Enter")
        page.get_by_text("Two region columns are available.", exact=False).wait_for()
        shot("clarification")

        # Answer — the trust trail arrives EXPANDED (do not click it)
        page.get_by_role("button").filter(has_text="customer region").click()
        page.get_by_text("East region generated the most", exact=False).wait_for()
        page.get_by_text("Revenue is calculated", exact=False).first.wait_for()
        shot("answer-trust-trail", pause=0.9)

        # SQL tab of the open trail
        page.get_by_role("button", name="SQL", exact=True).last.click()
        page.get_by_text("SUM(quantity", exact=False).first.wait_for()
        shot("trust-trail-sql", pause=0.2)

        # Table view of the result
        page.get_by_role("button", name="Table", exact=True).click()
        page.get_by_role("columnheader", name="region").wait_for()
        shot("result-table")

        # Ingest & profile — Add data menu
        page.get_by_role("button", name="Ingest & profile").click()
        page.get_by_role("button", name="Add data").click()
        page.get_by_role("button", name="Upload a file").wait_for()
        shot("add-data")

        # Connect-a-database form
        page.get_by_role("button", name="Connect a database").click()
        page.get_by_label("Connection name").wait_for()
        page.get_by_label("Database engine").select_option("postgres")
        shot("connect-database")

        browser.close()


if __name__ == "__main__":
    main()
