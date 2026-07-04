"""LLMGateway — the single, auditable egress path to the model (AC-16).

Everything the agentic layer sends to Claude passes through here. The gateway:
- caps the samples per column (only metadata + small samples leave the box),
- records every payload + prompt to an egress log (auditable; no bulk rows),
- calls a pluggable backend (real subscription, or a replay of recorded
  real responses for deterministic tests).

Raw bulk data never reaches this layer — the CatalogPayload carries only
schema, profiles, and capped samples by construction.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol

from analyst.domain.catalog import CatalogPayload

DEFAULT_SAMPLE_CAP = 5


@dataclass(frozen=True)
class LLMRequest:
    system_prompt: str
    prompt: str

    def key(self) -> str:
        """Stable content hash used to key recorded responses."""
        blob = f"{self.system_prompt}\x00{self.prompt}".encode()
        return hashlib.sha256(blob).hexdigest()


class LLMBackend(Protocol):
    def complete(self, request: LLMRequest) -> str: ...


@dataclass
class EgressLog:
    """Records exactly what crossed to the model. The AC-16 audit surface."""

    entries: list[dict] = field(default_factory=list)

    def record(self, payload: CatalogPayload, request: LLMRequest) -> None:
        self.entries.append(
            {
                "dataset": payload.dataset,
                "row_count": payload.row_count,
                "columns": [
                    {
                        "name": c.name,
                        "type": c.inferred_type.value,
                        "null_rate": c.null_rate,
                        "distinct_count": c.distinct_count,
                        "sample_count": len(c.samples),
                        "samples": [str(s) for s in c.samples],
                    }
                    for c in payload.columns
                ],
                "prompt_chars": len(request.prompt),
            }
        )

    def sent_value_count(self) -> int:
        """Total sample values ever sent — used to prove it's far below bulk."""
        return sum(len(c["samples"]) for e in self.entries for c in e["columns"])


MAX_SAMPLE_VALUE_LEN = 200  # SECURITY H7/M11: cap value LENGTH, not just count


def _cap_payload(payload: CatalogPayload, sample_cap: int) -> CatalogPayload:
    def _cap_value(value: object) -> object:
        text = str(value)
        return (
            text[:MAX_SAMPLE_VALUE_LEN] if len(text) > MAX_SAMPLE_VALUE_LEN else value
        )

    capped = tuple(
        dataclasses.replace(
            c, samples=tuple(_cap_value(s) for s in c.samples[:sample_cap])
        )
        for c in payload.columns
    )
    return dataclasses.replace(payload, columns=capped)


class LLMGateway:
    """The sole path to the model. Caps samples, logs egress, calls the backend."""

    def __init__(
        self,
        backend: LLMBackend,
        egress_log: EgressLog | None = None,
        sample_cap: int = DEFAULT_SAMPLE_CAP,
    ):
        self.backend = backend
        self.egress_log = egress_log if egress_log is not None else EgressLog()
        self.sample_cap = sample_cap

    def run(
        self,
        payload: CatalogPayload,
        system_prompt: str,
        render_prompt: Callable[[CatalogPayload], str],
    ) -> str:
        capped = _cap_payload(payload, self.sample_cap)
        # Governance invariant: every column carries at most `sample_cap` values.
        assert all(len(c.samples) <= self.sample_cap for c in capped.columns)
        request = LLMRequest(system_prompt=system_prompt, prompt=render_prompt(capped))
        self.egress_log.record(capped, request)
        return self.backend.complete(request)


# --------------------------------------------------------------------------- #
# Backends
# --------------------------------------------------------------------------- #
class StubBackend:
    """Returns a fixed response. For testing the gateway's governance, not the
    model — the response content is irrelevant to what was *sent*."""

    def __init__(self, response: str = ""):
        self.response = response

    def complete(self, request: LLMRequest) -> str:
        return self.response


class ReplayBackend:
    """Replays recorded REAL responses from a cassette file (deterministic)."""

    def __init__(self, cassette_path: str | Path):
        path = Path(cassette_path)
        self._records: dict[str, str] = (
            json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        )

    def complete(self, request: LLMRequest) -> str:
        key = request.key()
        if key not in self._records:
            raise KeyError(
                f"No recorded response for this prompt (key {key[:12]}…). "
                "Re-record with a live run."
            )
        return self._records[key]


class RecordingBackend:
    """Wraps a live backend and writes each real response to a cassette."""

    def __init__(self, inner: LLMBackend, cassette_path: str | Path):
        self.inner = inner
        self.path = Path(cassette_path)
        self._records: dict[str, str] = (
            json.loads(self.path.read_text(encoding="utf-8"))
            if self.path.exists()
            else {}
        )

    def complete(self, request: LLMRequest) -> str:
        response = self.inner.complete(request)
        self._records[request.key()] = response
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._records, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return response
