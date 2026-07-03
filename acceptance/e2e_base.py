"""Shared infrastructure for browser/HTTP-bound acceptance handler modules.

A feature that needs e2e binding creates ``acceptance/e2e_<slug>.py``:

    from acceptance.e2e_base import (
        ScenarioContext, make_registry, _e2e_stack, _e2e_fresh, expect_,
    )
    step, run_step = make_registry()

    @step(r"...step text...")
    def given_something(ctx: ScenarioContext) -> None: ...

    __all__ = ["ScenarioContext", "run_step", "_e2e_stack", "_e2e_fresh"]

and points its feature folder at it with a one-line ``.handlers`` file
(``acceptance.e2e_<slug>``) — the runner and generated conftest do the rest.

The session stack boots ONCE per pytest run: the fixtures API (ANALYST_FIXTURES=1)
+ the production frontend build (vite preview) on ephemeral ports + Chromium.
Per-scenario isolation: /api/_reset + a fresh browser context.
"""

from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND = REPO_ROOT / "frontend"

_STACK: dict[str, Any] = {}  # session: api/web URLs, browser; per-test: page


@dataclass
class ScenarioContext:
    tmp_path: Path
    scenario: str = ""
    spec: str = ""
    response: httpx.Response | None = None
    data: Any = None

    @property
    def api(self) -> str:
        return _STACK["api"]

    @property
    def web(self) -> str:
        return _STACK["web"]

    @property
    def page(self):  # noqa: ANN201 - playwright Page
        return _STACK["page"]


def make_registry() -> tuple[Callable, Callable]:
    """A fresh (step, run_step) pair for one handlers module."""
    registry: list[tuple[re.Pattern[str], Callable[..., None]]] = []

    def step(pattern: str) -> Callable[[Callable[..., None]], Callable[..., None]]:
        compiled = re.compile(pattern)

        def register(func: Callable[..., None]) -> Callable[..., None]:
            registry.append((compiled, func))
            return func

        return register

    def run_step(ctx: ScenarioContext, keyword: str, text: str) -> None:
        for pattern, func in registry:
            match = pattern.fullmatch(text)
            if match is None:
                continue
            try:
                func(ctx, **match.groupdict())
            except AssertionError as exc:
                pytest.fail(
                    f"{keyword} {text}\n  assertion: {exc}\n"
                    f"  scenario:  {ctx.scenario}\n  spec:      {ctx.spec}",
                    pytrace=False,
                )
            return
        pytest.fail(
            f"NOT YET IMPLEMENTED: {keyword} {text}\n"
            f"  scenario: {ctx.scenario}\n  spec:     {ctx.spec}",
            pytrace=False,
        )

    return step, run_step


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_http(url: str, timeout: float = 60.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if httpx.get(url, timeout=2.0).status_code < 500:
                return
        except httpx.HTTPError:
            time.sleep(0.2)
    raise RuntimeError(f"server at {url} did not come up within {timeout}s")


@pytest.fixture(scope="session", autouse=True)
def _e2e_stack():
    from playwright.sync_api import sync_playwright

    api_port, web_port = _free_port(), _free_port()
    api_url = f"http://127.0.0.1:{api_port}"
    web_url = f"http://127.0.0.1:{web_port}"
    procs: list[subprocess.Popen] = []
    try:
        procs.append(
            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "analyst.api.app:app",
                    "--port",
                    str(api_port),
                    "--log-level",
                    "warning",
                ],
                cwd=REPO_ROOT,
                env={**os.environ, "ANALYST_FIXTURES": "1"},
            )
        )
        # Test the real production build; preview inherits the /api proxy.
        subprocess.run(
            ["bun", "run", "build"],
            cwd=FRONTEND,
            check=True,
            capture_output=True,
            env={**os.environ, "ANALYST_API": api_url},
        )
        procs.append(
            subprocess.Popen(
                [
                    "bun",
                    "run",
                    "preview",
                    "--",
                    "--port",
                    str(web_port),
                    "--strictPort",
                    "--host",
                    "127.0.0.1",
                ],
                cwd=FRONTEND,
                env={**os.environ, "ANALYST_API": api_url},
                stdout=subprocess.DEVNULL,
            )
        )
        _wait_http(f"{api_url}/api/health")
        _wait_http(web_url)

        pw = sync_playwright().start()
        browser = pw.chromium.launch()
        _STACK.update(api=api_url, web=web_url, browser=browser, pw=pw)
        yield
    finally:
        if "browser" in _STACK:
            _STACK["browser"].close()
        if "pw" in _STACK:
            _STACK["pw"].stop()
        for proc in procs:
            proc.terminate()
        for proc in procs:
            proc.wait(timeout=10)
        _STACK.clear()


@pytest.fixture(autouse=True)
def _e2e_fresh():
    """Per-scenario isolation: seeded workspace + a fresh browser context."""
    httpx.post(f"{_STACK['api']}/api/_reset", timeout=10.0)
    context = _STACK["browser"].new_context()
    _STACK["page"] = context.new_page()
    yield
    context.close()
    _STACK.pop("page", None)


def expect_():  # lazy import so collecting never needs playwright installed
    from playwright.sync_api import expect

    expect.set_options(timeout=10_000)
    return expect
