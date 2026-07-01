"""Slice D — LLMGateway governance (AC-16) + Cataloguer (AC-4, AC-22).

The `live` test records a REAL cataloguing response (Claude subscription) into a
cassette; the default tests replay that real response deterministically.
Record with:  uv run pytest -m live tests/unit/test_agentic.py
"""

from pathlib import Path

import pytest

from analyst.agentic.cataloguer import Cataloguer
from analyst.agentic.gateway import (
    EgressLog,
    LLMGateway,
    ReplayBackend,
    StubBackend,
)
from analyst.domain.catalog import CatalogPayload, ColumnMetadata
from analyst.domain.types import ColumnType

CASSETTE = Path(__file__).parent.parent / "cassettes" / "cataloguer.json"


def _payload() -> CatalogPayload:
    """Deterministic fixture — identical for recording and replay."""
    return CatalogPayload(
        dataset="orders",
        row_count=1000,
        columns=(
            ColumnMetadata("order_id", ColumnType.INTEGER, 0.0, 1000, (1, 2, 3)),
            ColumnMetadata("customer", ColumnType.TEXT, 0.0, 812, ("alice", "bob")),
            ColumnMetadata(
                "amount", ColumnType.DECIMAL, 0.01, 640, (10.5, 20.0, 30.25)
            ),
            ColumnMetadata(
                "placed_at", ColumnType.DATETIME, 0.0, 1000, ("2024-01-15 09:30:00",)
            ),
        ),
    )


# --------------------------------------------------------------------------- #
# AC-16 — governance: only capped metadata/samples leave the box; audited.
# --------------------------------------------------------------------------- #
def test_gateway_caps_samples_and_logs_egress():
    log = EgressLog()
    gateway = LLMGateway(StubBackend("{}"), egress_log=log, sample_cap=2)
    bulky = CatalogPayload(
        dataset="big",
        row_count=100_000,
        columns=(
            ColumnMetadata("x", ColumnType.INTEGER, 0.0, 100_000, tuple(range(500))),
        ),
    )
    gateway.run(bulky, "sys", lambda p: "prompt")

    assert len(log.entries) == 1
    # samples capped to 2 — nowhere near the 100k rows
    assert log.entries[0]["columns"][0]["sample_count"] == 2
    assert log.sent_value_count() == 2
    assert log.sent_value_count() < bulky.row_count


def test_egress_log_never_contains_bulk_rows():
    log = EgressLog()
    gateway = LLMGateway(StubBackend("{}"), egress_log=log, sample_cap=5)
    gateway.run(_payload(), "sys", lambda p: "prompt")
    # Every column logged at most the cap; total far below any bulk table.
    for entry in log.entries:
        for col in entry["columns"]:
            assert col["sample_count"] <= 5


# --------------------------------------------------------------------------- #
# AC-4 — agent-authored catalog entry, via a recorded REAL response.
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(not CASSETTE.exists(), reason="cassette not recorded yet")
def test_cataloguer_produces_entry_from_recorded_response():
    gateway = LLMGateway(ReplayBackend(CASSETTE))
    entry = Cataloguer(gateway).catalog(_payload())
    assert entry.table_description.strip()
    names = {c.name for c in entry.columns}
    assert {"order_id", "customer", "amount", "placed_at"} <= names
    roles = {c.role for c in entry.columns}
    assert roles, "no roles inferred"


# --------------------------------------------------------------------------- #
# Live recorder — opt-in; hits the real subscription and writes the cassette.
# --------------------------------------------------------------------------- #
@pytest.mark.live
def test_record_live_cataloguing():
    from analyst.agentic.claude_backend import ClaudeAgentBackend
    from analyst.agentic.gateway import RecordingBackend

    gateway = LLMGateway(RecordingBackend(ClaudeAgentBackend(), CASSETTE))
    entry = Cataloguer(gateway).catalog(_payload())
    assert entry.columns, "live cataloguing returned no columns"
