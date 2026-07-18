"""DatasetRepository — the seam between the API and where data lives.

StoreRepository    → the real IngestionService + DatasetStore (DuckDB/Parquet),
                     the DEFAULT.
FixtureRepository  → in-memory domain objects (opt-in mock: ANALYST_FIXTURES=1).

Both return the same domain `DatasetSummary`; the API layer serializes it. The
repository owns only the *envelope* metadata the domain doesn't carry
(file name, status, ingested-at).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Protocol

from analyst.api import fixtures
from analyst.domain.dataset import DatasetSummary, RefreshResult
from analyst.domain.status import IngestionStatus

_LOG = logging.getLogger(__name__)


@dataclass
class DatasetRecord:
    """A dataset plus the API-envelope metadata the domain doesn't track."""

    summary: DatasetSummary
    file_name: str
    status: IngestionStatus = IngestionStatus.COMPLETE
    ingested_at: str | None = None
    started_at: float | None = None  # monotonic; drives simulated progress
    # Federated (connected-DB) tables are catalogued + visible.
    federated: bool = False
    # Feature 007 — a federated table whose data is ATTACHed into the store's
    # connection (scanner engine), so within-DB Q&A can run SQL against it.
    db_queryable: bool = False
    # Feature 009 — async cataloguing lifecycle for connected-DB tables:
    # "complete" | "pending" (background cataloguing) | "failed" (contained).
    catalog_status: str = "complete"

    @property
    def name(self) -> str:
        return self.summary.name


class DatasetRepository(Protocol):
    def list_datasets(self) -> list[DatasetRecord]: ...
    def get_dataset(self, name: str) -> DatasetRecord | None: ...
    def catalog(self) -> dict[str, object]: ...
    def delete(self, name: str) -> None: ...
    def ingest(self, file_name: str, content: bytes) -> list[DatasetRecord]: ...
    def status(self, name: str) -> tuple[IngestionStatus, str | None, int | None]: ...
    def refresh(self, name: str, file_name: str, content: bytes) -> RefreshResult: ...

    # Feature 013 — normalization lifecycle
    def normalization(self, name: str) -> tuple[list, list]: ...
    def approve_normalization(self, name: str, rule_id: str) -> None: ...
    def dismiss_normalization(self, name: str, rule_id: str) -> None: ...
    def revoke_normalization(self, name: str, rule_id: str) -> None: ...

    # Feature 015 — dashboards (agent-assembled, filterable widget grids)
    def dashboards(self) -> list: ...
    def put_dashboard(self, dashboard: Any) -> None: ...
    def create_dashboard(self, request: str) -> dict: ...
    def remove_widget(self, dashboard_id: str, widget_id: str) -> None: ...
    def edit_dashboard(self, dashboard_id: str, request: str) -> dict: ...
    def run_dashboard(self, dashboard_id: str, filters: list) -> dict: ...
    def drill_dashboard(
        self, dashboard_id: str, widget_id: str, filters: list
    ) -> object: ...
    def delete_dashboard(self, dashboard_id: str) -> None: ...

    # Feature 016 — catalog curation (answer clarifications, suggest corrections)
    def curation(self, name: str) -> dict: ...
    def answer_clarification(self, name: str, column: str, answer: str) -> None: ...
    def suggest_correction(self, name: str, column: str | None, note: str) -> None: ...

    # Feature 014 — saved charts (saved question + config; re-run on open)
    def charts(self) -> list: ...
    def save_chart(self, **kwargs: Any) -> object: ...
    def open_chart(self, chart_id: str) -> object: ...
    def rename_chart(self, chart_id: str, name: str) -> None: ...
    def delete_chart(self, chart_id: str) -> None: ...

    # Feature 005 hooks — connection-backed datasets (routes/databases.py owns
    # the federation logic; these only add/remove the resulting records).
    def add_records(self, records: list[DatasetRecord]) -> None: ...
    def remove_records(self, names: list[str]) -> None: ...

    # Feature 010 hook — retroactive re-cataloguing of the existing tables a
    # new relationship touches (bounded to the affected set, never O(workspace)).
    def recatalogue_affected(self, new_names: list[str]) -> None: ...

    # Feature 010 hooks — connected-DB catalog persistence (AC-6/AC-7). Keyed
    # naturally by the record name ``<connection>.<table>``; the fingerprint
    # detects a schema change while the service was down.
    def persist_catalog(
        self,
        name: str,
        entry: object,
        fingerprint: str | None = None,
        profile: object | None = None,
    ) -> None: ...
    def load_persisted_catalog(
        self, name: str
    ) -> "tuple[object, str | None, object | None] | None": ...
    def persisted_connection_tables(self, connection: str) -> list[str]: ...


# --------------------------------------------------------------------------- #
# Fixtures — the mock, in Python.
# --------------------------------------------------------------------------- #
_PHASES = ["materializing", "profiling", "cataloguing"]
_SIM_SECONDS = 3.0  # how long a simulated ingest "runs"


class FixtureRepository:
    """In-memory workspace seeded from `api.fixtures`. Ingest is simulated."""

    def __init__(self) -> None:
        self._records: dict[str, DatasetRecord] = {}
        for i, summary in enumerate(fixtures.seed()):
            self._records[summary.name] = DatasetRecord(
                summary=summary,
                file_name=f"{summary.name}.csv",
                status=IngestionStatus.COMPLETE,
                ingested_at=f"2025-12-1{i}",
            )
        # Feature 013: one seeded proposal (sales.region case variants) so the
        # workbench approve/dismiss flow is drivable in demos and browser e2e.
        from analyst.domain.normalization import group_variants, rule_for

        seeded = rule_for(
            "billing_region",
            group_variants(
                {"East": 41, "east": 7, "EAST": 3, "North": 60, "South": 52, "West": 37}
            ),
        )
        self._norm: dict[str, dict[str, list]] = {
            "sales": {"proposals": [seeded], "applied": []}
        }
        # Feature 014: saved charts (in-memory).
        self._charts: dict[str, Any] = {}
        # Feature 016: curation state (in-memory).
        self._curation: dict[str, dict] = {}
        # Feature 015: dashboards (in-memory, canned assembly/run).
        self._dashboards: dict[str, Any] = {}

    def list_datasets(self) -> list[DatasetRecord]:
        return list(self._records.values())

    def get_dataset(self, name: str) -> DatasetRecord | None:
        return self._records.get(name)

    def catalog(self) -> dict[str, object]:
        return {
            r.name: r.summary.catalog
            for r in self._records.values()
            if r.summary.catalog
        }

    def delete(self, name: str) -> None:
        self._records.pop(name, None)

    def add_records(self, records: list[DatasetRecord]) -> None:
        for record in records:
            self._records[record.name] = record

    def remove_records(self, names: list[str]) -> None:
        for name in names:
            self._records.pop(name, None)

    def recatalogue_affected(self, new_names: list[str]) -> None:
        """No-op: fixture catalogs are static seed data (feature 010)."""

    # Feature 015 — dashboards over canned data (assembly, run, drill are
    # deterministic so demos and browser e2e are drivable).
    def dashboards(self) -> list:
        return list(self._dashboards.values())

    def _canned_dashboard(self):  # noqa: ANN202
        from analyst.domain.dashboards import (
            Dashboard,
            DashboardFilter,
            DashboardWidget,
        )

        return Dashboard(
            dashboard_id="sales-overview",
            name="Sales overview",
            widgets=(
                DashboardWidget(
                    widget_id="revenue-by-region",
                    question="Revenue by region",
                    sql='SELECT billing_region, SUM(quantity*unit_price) FROM "sales" WHERE /*FILTERS*/ 1=1 GROUP BY 1',
                    chart_type="bar",
                    title="Revenue by region",
                    source="sales",
                ),
                DashboardWidget(
                    widget_id="customer-count",
                    question="How many customers?",
                    sql='SELECT COUNT(*) FROM "customers" WHERE /*FILTERS*/ 1=1',
                    chart_type="stat",
                    title="Customers",
                    source="customers",
                ),
                DashboardWidget(
                    widget_id="recent-orders",
                    question="Recent orders",
                    sql='SELECT * FROM "sales" WHERE /*FILTERS*/ 1=1 ORDER BY order_date DESC',
                    chart_type="none",
                    title="Recent orders",
                    source="sales",
                ),
            ),
            filters=(DashboardFilter(column="billing_region", label="Region"),),
        )

    def put_dashboard(self, dashboard: Any) -> None:
        self._dashboards[dashboard.dashboard_id] = dashboard

    def create_dashboard(self, request: str) -> dict:
        from analyst.agentic.dashboards import ClarificationSpec

        if "performance" in request.lower():
            return {
                "dashboard": None,
                "clarification": ClarificationSpec(
                    question="Which performance do you mean?",
                    options=["Sales performance", "Fulfilment performance"],
                ),
            }
        dashboard = self._canned_dashboard()
        self._dashboards[dashboard.dashboard_id] = dashboard
        return {"dashboard": dashboard, "clarification": None}

    def edit_dashboard(self, dashboard_id: str, request: str) -> dict:
        from analyst.domain.dashboards import UnknownDashboardError

        if dashboard_id not in self._dashboards:
            raise UnknownDashboardError(dashboard_id)
        return {"dashboard": self._dashboards[dashboard_id], "clarification": None}

    def run_dashboard(self, dashboard_id: str, filters: list) -> dict:
        from analyst.api.schemas import (
            AnswerResult,
            ChartPoint,
            StatBlock,
            TableBlock,
            TrustTrailSchema,
        )
        from analyst.domain.dashboards import UnknownDashboardError

        dashboard = self._dashboards.get(dashboard_id)
        if dashboard is None:
            raise UnknownDashboardError(dashboard_id)
        filtered = bool(filters)
        points = (
            [("East", 84200.0)]
            if filtered
            else [
                ("North", 96400.0),
                ("East", 84200.0),
                ("South", 61800.0),
                ("West", 43900.0),
            ]
        )
        trail = TrustTrailSchema(
            assumptions=["Canned demo numbers."],
            lineage=["source: sales"],
            sql=dashboard.widgets[0].sql,
        )
        revenue = AnswerResult(
            query_id="dash-revenue",
            summary="Revenue by region.",
            chart_type="bar",
            chart_title="Revenue by region",
            highlight=points[0][0],
            nice_max=100000.0,
            tick_step=25000.0,
            chart_data=[ChartPoint(label=k, value=v) for k, v in points],
            table=TableBlock(
                columns=["region", "total"], rows=[[k, v] for k, v in points]
            ),
            trust_trail=trail,
        )
        customers = AnswerResult(
            query_id="dash-customers",
            summary="Customers: 11,204.",
            chart_type="stat",
            chart_title="Customers",
            stat=StatBlock(value="11,204", label="Customers", sub="canned"),
            trust_trail=TrustTrailSchema(
                assumptions=["Canned demo numbers."],
                lineage=["source: customers"],
                sql=dashboard.widgets[1].sql,
            ),
        )
        return {
            "dashboard": dashboard,
            "widgets": {
                "revenue-by-region": {
                    "answer": revenue,
                    "error": None,
                    "unaffected_by": [],
                },
                "customer-count": {
                    "answer": customers,
                    "error": None,
                    "unaffected_by": ["billing_region"] if filtered else [],
                },
                "recent-orders": {
                    "answer": AnswerResult(
                        query_id="dash-orders",
                        summary="Recent orders.",
                        chart_type="none",
                        table=TableBlock(
                            columns=["order_id", "billing_region", "amount"],
                            rows=[
                                [f"ORD-1000{i:02d}", region, 50.0 + i]
                                for i, region in enumerate(
                                    ["East", "North", "South", "West"] * 3
                                )
                            ],
                        ),
                        trust_trail=TrustTrailSchema(
                            assumptions=["Canned demo numbers."],
                            lineage=["source: sales"],
                            sql=dashboard.widgets[2].sql,
                        ),
                    ),
                    "error": None,
                    "unaffected_by": [],
                },
            },
        }

    def drill_dashboard(
        self, dashboard_id: str, widget_id: str, filters: list
    ) -> object:
        from analyst.api.schemas import AnswerResult, TableBlock, TrustTrailSchema
        from analyst.domain.dashboards import UnknownDashboardError

        if dashboard_id not in self._dashboards:
            raise UnknownDashboardError(dashboard_id)
        return AnswerResult(
            query_id="dash-drill",
            summary="Rows behind the widget.",
            chart_type="none",
            table=TableBlock(
                columns=["order_id", "billing_region", "amount"],
                rows=[["ORD-100001", "East", 129.5], ["ORD-100002", "East", 88.0]],
            ),
            trust_trail=TrustTrailSchema(
                assumptions=[], lineage=["source: sales"], sql="SELECT *"
            ),
        )

    def delete_dashboard(self, dashboard_id: str) -> None:
        from analyst.domain.dashboards import UnknownDashboardError

        if dashboard_id not in self._dashboards:
            raise UnknownDashboardError(dashboard_id)
        del self._dashboards[dashboard_id]

    def remove_widget(self, dashboard_id: str, widget_id: str) -> None:
        import dataclasses

        from analyst.domain.dashboards import UnknownDashboardError

        dashboard = self._dashboards.get(dashboard_id)
        if dashboard is None:
            raise UnknownDashboardError(dashboard_id)
        self._dashboards[dashboard_id] = dataclasses.replace(
            dashboard,
            widgets=tuple(w for w in dashboard.widgets if w.widget_id != widget_id),
        )

    # Feature 016 — catalog curation over the in-memory entries (templated
    # completion; deterministic for demos and browser e2e).
    def curation(self, name: str) -> dict:
        state = self._curation.get(name, {})
        return {"columns": state.get("columns", {}), "table": state.get("table")}

    def answer_clarification(self, name: str, column: str, answer: str) -> None:
        import dataclasses

        from analyst.domain.catalog import UnknownCurationError

        if not answer.strip():
            raise ValueError("An answer is required.")
        record = self._records[name]
        entry = record.summary.catalog
        if entry is None:
            raise UnknownCurationError(name)
        clarification = next(
            (c for c in entry.clarifications if c.column == column), None
        )
        if clarification is None:
            raise UnknownCurationError(column)
        columns = tuple(
            dataclasses.replace(
                c, description=f"{answer.strip()} (settled by the user)."
            )
            if c.name == column
            else c
            for c in entry.columns
        )
        clars = tuple(c for c in entry.clarifications if c is not clarification)
        record.summary = dataclasses.replace(
            record.summary,
            catalog=dataclasses.replace(entry, columns=columns, clarifications=clars),
        )
        self._curation.setdefault(name, {}).setdefault("columns", {})[column] = {
            "kind": "answer",
            "input": answer.strip(),
            "description": f"{answer.strip()} (settled by the user).",
            "pending_reconciliation": False,
        }

    def suggest_correction(self, name: str, column: str | None, note: str) -> None:
        import dataclasses

        from analyst.domain.catalog import UnknownCurationError

        if not note.strip():
            raise ValueError("A suggestion is required.")
        record = self._records[name]
        entry = record.summary.catalog
        if entry is None:
            raise UnknownCurationError(name)
        stamp = {
            "kind": "correction",
            "input": note.strip(),
            "description": note.strip(),
            "pending_reconciliation": False,
        }
        if column is None:
            record.summary = dataclasses.replace(
                record.summary,
                catalog=dataclasses.replace(entry, table_description=note.strip()),
            )
            self._curation.setdefault(name, {})["table"] = stamp
            return
        if all(c.name != column for c in entry.columns):
            raise UnknownCurationError(column)
        columns = tuple(
            dataclasses.replace(c, description=note.strip()) if c.name == column else c
            for c in entry.columns
        )
        record.summary = dataclasses.replace(
            record.summary, catalog=dataclasses.replace(entry, columns=columns)
        )
        self._curation.setdefault(name, {}).setdefault("columns", {})[column] = stamp

    # Feature 014 — saved charts (in-memory; open returns a canned answer
    # shaped from fixture data so the browser flow is drivable in demos/e2e).
    def charts(self) -> list:
        return list(self._charts.values())

    def save_chart(self, **kwargs: Any) -> object:
        from analyst.domain.charts import SavedChart, chart_id_for

        chart_id = chart_id_for(str(kwargs["name"]), set(self._charts))
        chart = SavedChart(
            chart_id=chart_id,
            name=str(kwargs["name"]),
            question=str(kwargs.get("question", "")),
            sql=str(kwargs["sql"]),
            chart_type=str(kwargs.get("chart_type", "bar")),
            title=str(kwargs.get("title") or kwargs["name"]),
            datasets=tuple(kwargs.get("datasets", ()) or ()),
            assumptions=tuple(kwargs.get("assumptions", ()) or ()),
            lineage=tuple(kwargs.get("lineage", ()) or ()),
        )
        self._charts[chart_id] = chart
        return chart

    def open_chart(self, chart_id: str) -> object:
        from analyst.api.schemas import (
            AnswerResult,
            ChartPoint,
            TableBlock,
            TrustTrailSchema,
        )
        from analyst.domain.charts import UnknownChartError

        chart = self._charts.get(chart_id)
        if chart is None:
            raise UnknownChartError(chart_id)
        points = [
            ("North", 96400.0),
            ("East", 84200.0),
            ("South", 61800.0),
            ("West", 43900.0),
        ]
        return AnswerResult(
            query_id=f"chart-{chart_id}",
            summary=f"{chart.title}. North leads at 96,400.",
            chart_type=chart.chart_type
            if chart.chart_type in {"bar", "line"}
            else "bar",
            chart_title=chart.title,
            highlight="North",
            nice_max=100000.0,
            tick_step=25000.0,
            chart_data=[ChartPoint(label=k, value=v) for k, v in points],
            table=TableBlock(
                columns=["region", "total"], rows=[[k, v] for k, v in points]
            ),
            trust_trail=TrustTrailSchema(
                assumptions=list(chart.assumptions)
                or ["Saved chart — re-run against current data."],
                lineage=list(chart.lineage)
                or [f"datasets: {', '.join(chart.datasets) or 'sales'}"],
                sql=chart.sql,
            ),
        )

    def rename_chart(self, chart_id: str, name: str) -> None:
        import dataclasses

        from analyst.domain.charts import UnknownChartError

        if chart_id not in self._charts:
            raise UnknownChartError(chart_id)
        self._charts[chart_id] = dataclasses.replace(self._charts[chart_id], name=name)

    def delete_chart(self, chart_id: str) -> None:
        from analyst.domain.charts import UnknownChartError

        if chart_id not in self._charts:
            raise UnknownChartError(chart_id)
        del self._charts[chart_id]

    # Feature 013 — normalization lifecycle over the seeded in-memory state.
    def normalization(self, name: str) -> tuple[list, list]:
        state = self._norm.get(name, {"proposals": [], "applied": []})
        return list(state["proposals"]), list(state["applied"])

    def _take_proposal(self, name: str, rule_id: str):  # noqa: ANN202
        from analyst.domain.normalization import UnknownNormalizationError

        state = self._norm.setdefault(name, {"proposals": [], "applied": []})
        rule = next((r for r in state["proposals"] if r.rule_id == rule_id), None)
        if rule is None:
            raise UnknownNormalizationError(rule_id)
        state["proposals"].remove(rule)
        return state, rule

    def approve_normalization(self, name: str, rule_id: str) -> None:
        state, rule = self._take_proposal(name, rule_id)
        state["applied"].append(rule)

    def dismiss_normalization(self, name: str, rule_id: str) -> None:
        self._take_proposal(name, rule_id)

    def revoke_normalization(self, name: str, rule_id: str) -> None:
        from analyst.domain.normalization import UnknownNormalizationError

        state = self._norm.setdefault(name, {"proposals": [], "applied": []})
        rule = next((r for r in state["applied"] if r.rule_id == rule_id), None)
        if rule is None:
            raise UnknownNormalizationError(rule_id)
        state["applied"].remove(rule)
        state["proposals"].append(rule)

    def persist_catalog(
        self,
        name: str,
        entry: object,
        fingerprint: str | None = None,
        profile: object | None = None,
    ) -> None:
        """No-op: the fixture workspace has no disk (feature 010)."""

    def load_persisted_catalog(
        self, name: str
    ) -> tuple[object, str | None, object | None] | None:
        return None

    def persisted_connection_tables(self, connection: str) -> list[str]:
        return []

    def ingest(self, file_name: str, content: bytes) -> list[DatasetRecord]:
        # Mirror the real engine's validation so the mock can't hide the
        # rejected-upload path (defect regression, exploratory 2026-07-02).
        if not content.strip():
            from analyst.engine.reader import EmptyFileError

            raise EmptyFileError("The file is empty — there is no data to ingest.")
        summary = fixtures.uploaded_transactions()
        record = DatasetRecord(
            summary=summary,
            file_name=file_name or f"{summary.name}.csv",
            status=IngestionStatus.IN_PROGRESS,
            ingested_at="2026-07-01",
            started_at=time.monotonic(),
        )
        self._records[summary.name] = record
        return [record]

    def status(self, name: str) -> tuple[IngestionStatus, str | None, int | None]:
        record = self._records.get(name)
        if record is None:
            return IngestionStatus.FAILED, None, None
        if (
            record.status is not IngestionStatus.IN_PROGRESS
            or record.started_at is None
        ):
            return record.status, None, 100
        elapsed = time.monotonic() - record.started_at
        if elapsed >= _SIM_SECONDS:
            record.status = IngestionStatus.COMPLETE
            record.started_at = None
            return IngestionStatus.COMPLETE, None, 100
        frac = elapsed / _SIM_SECONDS
        phase = _PHASES[min(len(_PHASES) - 1, int(frac * len(_PHASES)))]
        return IngestionStatus.IN_PROGRESS, phase, int(frac * 100)

    def refresh(self, name: str, file_name: str, content: bytes) -> RefreshResult:
        """Simulated refresh: conforming data, new non-destructive version."""
        record = self._records.get(name)
        if record is None:
            raise KeyError(name)
        return RefreshResult(
            dataset_name=name,
            replaced=True,
            version=2,
            profile=record.summary.profile,
        )


# --------------------------------------------------------------------------- #
# Real store — wraps the implemented feature-001 service.
# --------------------------------------------------------------------------- #
class StoreRepository:
    """Adapts the real IngestionService/DatasetStore to the repository port.

    Only feature-001 file ingestion is wired; catalogs come from the summaries
    the service returns. Requires ANALYST_DATA_DIR.
    """

    def __init__(
        self,
        data_dir: str,
        cataloguer: object = None,
        curator: object = None,
        assembler: object = None,
    ) -> None:
        import tempfile

        from analyst.engine.store import DatasetStore
        from analyst.service.ingestion import IngestionService

        self._tempfile = tempfile
        self.store = DatasetStore(data_dir)
        # Feature 010: cataloguing sees the workspace — the service pulls the
        # current catalogs (files AND connected-DB records) on each ingest.
        self.service = IngestionService(
            self.store,
            cataloguer=cataloguer,  # type: ignore[arg-type]
            catalog_source=lambda: {
                name: record.summary.catalog for name, record in self._records.items()
            },
        )
        self.curator: Any = curator
        self.assembler: Any = assembler
        self._records: dict[str, DatasetRecord] = {}
        self._rehydrate()

    def _rehydrate(self) -> None:
        """Rebuild the dataset registry from the persisted store (HIGH H2).

        The DuckDB catalog + Parquet survive a restart; without this the API
        would show an empty workspace though the data is all on disk. Catalog
        entries are reloaded from their persisted sidecar when present.
        """
        from analyst.domain.dataset import DatasetSummary

        for name in self.store.datasets():
            # Feature 013: re-assert approved normalization rules BEFORE
            # profiling, so the record's profile tells the standardized truth.
            try:
                self._apply_active_normalization(name)
            except Exception:  # noqa: BLE001 - a broken overlay must not abort boot
                _LOG.warning("could not re-apply normalization for %r", name)
            try:
                profile = self.store.profile(name)
            except Exception:  # noqa: BLE001 - a broken relation shouldn't abort boot
                continue
            try:
                # Review #3: a corrupt/schema-drifted sidecar must NOT abort boot
                # and lose every healthy dataset — that table just loses its
                # cached catalog (it re-catalogues on demand).
                catalog = _load_catalog_sidecar(self.store.base_dir, name)
            except Exception:  # noqa: BLE001
                _LOG.warning("ignoring unreadable catalog sidecar for %r", name)
                catalog = None
            if catalog is not None:
                # Feature 016: human-settled meanings are sticky across boots.
                catalog = self._apply_curation_overlay(name, catalog)
            self._records[name] = DatasetRecord(
                summary=DatasetSummary(name=name, profile=profile, catalog=catalog),
                file_name=f"{name}.csv",
                status=IngestionStatus.COMPLETE,
            )

    def list_datasets(self) -> list[DatasetRecord]:
        return list(self._records.values())

    def get_dataset(self, name: str) -> DatasetRecord | None:
        return self._records.get(name)

    def catalog(self) -> dict[str, object]:
        return {
            r.name: r.summary.catalog
            for r in self._records.values()
            if r.summary.catalog
        }

    def delete(self, name: str) -> None:
        self.service.delete(name)
        self._records.pop(name, None)
        _catalog_sidecar(self.store.base_dir, name).unlink(missing_ok=True)

    def add_records(self, records: list[DatasetRecord]) -> None:
        for record in records:
            self._records[record.name] = record

    def remove_records(self, names: list[str]) -> None:
        for name in names:
            self._records.pop(name, None)

    def ingest(self, file_name: str, content: bytes) -> list[DatasetRecord]:
        # Write under the REAL file name (in a temp dir) — the service derives
        # the dataset name from the file's stem, so a NamedTemporaryFile would
        # produce garbage dataset names like "tmps9jbs9y1". SECURITY (C1): the
        # name is basename-sanitized so a `../`-laden upload can't escape the dir.
        with self._tempfile.TemporaryDirectory() as tmp_dir:
            from pathlib import Path

            tmp_path = Path(tmp_dir) / _safe_upload_name(file_name)
            tmp_path.write_bytes(content)
            result = self.service.ingest(tmp_path)
        out: list[DatasetRecord] = []
        for summary in result.datasets:
            # Persist the agent-authored catalog so it survives a restart (H2).
            _save_catalog_sidecar(self.store.base_dir, summary.name, summary.catalog)
            rec = DatasetRecord(
                summary=summary,
                file_name=file_name,
                status=IngestionStatus.COMPLETE,
                ingested_at=time.strftime("%Y-%m-%d"),
            )
            self._records[summary.name] = rec
            out.append(rec)
        # Feature 010 (AC-4): the new datasets may have created relationships
        # to existing tables — refresh those tables' meanings, and only those.
        self.recatalogue_affected([r.name for r in out])
        return out

    def recatalogue_affected(self, new_names: list[str]) -> None:
        """Re-catalogue ONLY the existing tables a new relationship touches
        (feature 010, AC-4/AC-5). Any failure is contained: the affected table
        keeps its prior entry and the ingest/connect is never broken (AC-10).
        """
        import dataclasses

        try:
            rels = tuple(self.store.discover_relationships(include_federated=True))
        except Exception:  # noqa: BLE001 - discovery failure never breaks ingest
            return
        new = set(new_names)
        affected: set[str] = set()
        for r in rels:
            if r.child_table in new and r.parent_table not in new:
                affected.add(r.parent_table)
            elif r.parent_table in new and r.child_table not in new:
                affected.add(r.child_table)
        affected &= set(self._records) - new
        if not affected:
            return
        catalogs = {n: rec.summary.catalog for n, rec in self._records.items()}
        for name in sorted(affected):
            record = self._records[name]
            try:
                entry = self._derive_entry(name, record.summary.profile, rels, catalogs)
            except Exception:  # noqa: BLE001 - AC-10: keep the prior entry
                _LOG.warning("re-cataloguing %r failed; keeping prior entry", name)
                continue
            record.summary = dataclasses.replace(record.summary, catalog=entry)
            # A federated record keeps its schema fingerprint (AC-7) and its
            # profile (011: unreachable display) so the retroactive refresh
            # doesn't degrade the sidecar.
            fed = record.federated
            _save_catalog_sidecar(
                self.store.base_dir,
                name,
                entry,
                _schema_fingerprint(record.summary.profile) if fed else None,
                record.summary.profile if fed else None,
            )

    def persist_catalog(
        self,
        name: str,
        entry: object,
        fingerprint: str | None = None,
        profile: object | None = None,
    ) -> None:
        """Persist a connected-DB table's catalog (feature 010, AC-6)."""
        _save_catalog_sidecar(self.store.base_dir, name, entry, fingerprint, profile)

    def load_persisted_catalog(
        self, name: str
    ) -> tuple[object, str | None, object | None] | None:
        """The persisted (entry, fingerprint, profile) for a record, or None."""
        try:
            return _load_catalog_sidecar_with_fingerprint(self.store.base_dir, name)
        except Exception:  # noqa: BLE001 - a corrupt sidecar just re-derives
            _LOG.warning("ignoring unreadable catalog sidecar for %r", name)
            return None

    def persisted_connection_tables(self, connection: str) -> list[str]:
        """Record names with a persisted sidecar under this connection
        (feature 011: what an unreachable connection can still show)."""
        suffix = ".catalog.json"
        return sorted(
            path.name[: -len(suffix)]
            for path in self.store.base_dir.glob(f"{connection}.*{suffix}")
        )

    def _derive_entry(self, name: str, profile, rels, catalogs):  # noqa: ANN001
        """One table's catalog entry, via the same path that catalogued it:
        the configured cataloguer when present, else offline enrich — always
        in the context of the current workspace (feature 010)."""
        from analyst.domain.workspace_context import build_workspace_context

        context = build_workspace_context(catalogs, rels).for_table(name)
        cataloguer = self.service.cataloguer
        if cataloguer is not None:
            from analyst.domain.catalog import payload_from_profile

            return cataloguer.catalog(
                payload_from_profile(name, profile), rels, context=context
            )
        from analyst.agentic import enrich

        return enrich.catalog_entry(name, profile, rels, context=context)

    def status(self, name: str) -> tuple[IngestionStatus, str | None, int | None]:
        record = self._records.get(name)
        if record is None:
            return IngestionStatus.FAILED, None, None
        return record.status, None, 100

    def refresh(self, name: str, file_name: str, content: bytes) -> RefreshResult:
        """Real refresh: schema-validated, versioned (feature-001 semantics)."""
        record = self._records.get(name)
        if record is None:
            raise KeyError(name)
        suffix = "." + file_name.rsplit(".", 1)[-1] if "." in file_name else ".csv"
        with self._tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        result = self.service.refresh(name, tmp_path)
        if result.replaced and result.profile is not None:
            import dataclasses

            record.summary = dataclasses.replace(record.summary, profile=result.profile)
            # Feature 013: a refresh re-registers the plain view — re-assert the
            # approved rules and re-profile so the standard holds across versions.
            if self._apply_active_normalization(name):
                self._reprofile(name)
        return result

    # ------------------------------------------------------------------ #
    # Feature 013 — normalization lifecycle (propose/approve/dismiss/revoke)
    # ------------------------------------------------------------------ #
    def normalization(self, name: str) -> tuple[list, list]:
        """(pending proposals, applied rules) for one dataset."""
        from analyst.domain.normalization import NormalizationRule
        from analyst.engine.normalization import detect

        if name not in self._records:
            raise KeyError(name)
        decisions = self._normalization_decisions(name)
        rules = detect(self.store, name, self.store.profile(name))
        proposals = [rule for rule in rules if rule.column not in decisions]
        applied = [
            NormalizationRule(
                rule_id=f"norm:{column}",
                column=column,
                groups=(),
                mapping=dict(decision["mapping"]),
                description=str(decision["description"]),
            )
            for column, decision in sorted(decisions.items())
            if decision["status"] == "approved"
        ]
        return proposals, applied

    def approve_normalization(self, name: str, rule_id: str) -> None:
        from analyst.domain.normalization import UnknownNormalizationError

        proposals, _ = self.normalization(name)
        rule = next((r for r in proposals if r.rule_id == rule_id), None)
        if rule is None:
            raise UnknownNormalizationError(rule_id)
        decisions = self._normalization_decisions(name)
        decisions[rule.column] = {
            "status": "approved",
            "mapping": rule.mapping,
            "description": rule.description,
        }
        self._save_normalization(name, decisions)
        self._apply_active_normalization(name)
        self._reprofile(name)

    def dismiss_normalization(self, name: str, rule_id: str) -> None:
        from analyst.domain.normalization import UnknownNormalizationError

        proposals, _ = self.normalization(name)
        rule = next((r for r in proposals if r.rule_id == rule_id), None)
        if rule is None:
            raise UnknownNormalizationError(rule_id)
        decisions = self._normalization_decisions(name)
        decisions[rule.column] = {"status": "dismissed"}
        self._save_normalization(name, decisions)

    def revoke_normalization(self, name: str, rule_id: str) -> None:
        from analyst.domain.normalization import UnknownNormalizationError

        decisions = self._normalization_decisions(name)
        column = rule_id.removeprefix("norm:")
        if decisions.get(column, {}).get("status") != "approved":
            raise UnknownNormalizationError(rule_id)
        del decisions[column]
        self._save_normalization(name, decisions)
        self._apply_active_normalization(name)
        self._reprofile(name)

    def _normalization_decisions(self, name: str) -> dict:
        import json

        sidecar = _normalization_sidecar(self.store.base_dir, name)
        if not sidecar.is_file():
            return {}
        try:
            return dict(json.loads(sidecar.read_text())["columns"])
        except Exception:  # noqa: BLE001 - corrupt sidecar = no decisions, never a crash
            _LOG.warning("ignoring unreadable normalization sidecar for %r", name)
            return {}

    def _save_normalization(self, name: str, decisions: dict) -> None:
        import json

        sidecar = _normalization_sidecar(self.store.base_dir, name)
        if decisions:
            sidecar.write_text(json.dumps({"columns": decisions}, indent=2))
        elif sidecar.is_file():
            sidecar.unlink()

    def _apply_active_normalization(self, name: str) -> bool:
        """Re-assert the view overlay from persisted decisions. True if any
        approved mapping is in effect."""
        mappings = {
            column: dict(decision["mapping"])
            for column, decision in self._normalization_decisions(name).items()
            if decision["status"] == "approved"
        }
        self.store.apply_normalization(name, mappings)
        return bool(mappings)

    def _reprofile(self, name: str) -> None:
        import dataclasses

        record = self._records[name]
        record.summary = dataclasses.replace(
            record.summary, profile=self.store.profile(name)
        )

    # ------------------------------------------------------------------ #
    # Feature 014 — saved charts: persist the validated SQL + config in a
    # workspace sidecar; OPEN re-runs the SQL against current data (never a
    # snapshot). The stored SQL is re-guarded on every open.
    # ------------------------------------------------------------------ #
    def charts(self) -> list:
        from analyst.domain.charts import SavedChart

        return [
            SavedChart(chart_id=cid, **payload)
            for cid, payload in self._load_charts().items()
        ]

    def save_chart(self, **kwargs: Any) -> object:
        from analyst.domain.charts import SavedChart, chart_id_for

        charts = self._load_charts()
        name = str(kwargs["name"])
        sql = str(kwargs["sql"])
        payload: dict[str, Any] = {
            "name": name,
            "question": str(kwargs.get("question", "")),
            "sql": sql,
            "chart_type": str(kwargs.get("chart_type", "bar")),
            "title": str(kwargs.get("title", name)),
            "datasets": tuple(kwargs.get("datasets", ()) or ()),
            "assumptions": tuple(kwargs.get("assumptions", ()) or ()),
            "lineage": tuple(kwargs.get("lineage", ()) or ()),
        }
        problems = self.store.validation_problems(sql)
        if problems:
            raise ValueError(problems[0])
        chart_id = chart_id_for(name, set(charts))
        charts[chart_id] = payload
        self._save_charts(charts)
        return SavedChart(chart_id=chart_id, **payload)

    def open_chart(self, chart_id: str) -> object:
        """Re-run the stored, validated SQL and shape it exactly as Q&A
        shapes answers — one interpretation path for both surfaces."""
        from analyst.api.qa import shape_answer
        from analyst.domain.charts import ChartDataGoneError
        from analyst.domain.query import PlanAction, QueryPlan
        from analyst.engine.query import run_select

        chart = self._require_chart(chart_id)
        problems = self.store.validation_problems(chart["sql"])
        if problems:
            raise ChartDataGoneError(
                f"This chart's data is gone or has changed shape: {problems[0]}"
            )
        result = run_select(self.store, chart["sql"])
        plan = QueryPlan(
            action=PlanAction.ANSWER,
            sql=chart["sql"],
            title=chart["title"],
            assumptions=tuple(chart.get("assumptions", ())),
            lineage=tuple(chart.get("lineage", ())),
        )
        answer = shape_answer(plan, result)
        if chart["chart_type"] in {"bar", "line"} and answer.chart_data:
            answer.chart_type = chart["chart_type"]
        return answer

    def rename_chart(self, chart_id: str, name: str) -> None:
        charts = self._load_charts()
        self._require_chart(chart_id)
        charts[chart_id]["name"] = name
        self._save_charts(charts)

    def delete_chart(self, chart_id: str) -> None:
        charts = self._load_charts()
        self._require_chart(chart_id)
        del charts[chart_id]
        self._save_charts(charts)

    def _require_chart(self, chart_id: str) -> dict:
        from analyst.domain.charts import UnknownChartError

        charts = self._load_charts()
        if chart_id not in charts:
            raise UnknownChartError(chart_id)
        return charts[chart_id]

    def _load_charts(self) -> dict:
        import json
        from pathlib import Path

        sidecar = Path(str(self.store.base_dir)) / "charts.json"
        if not sidecar.is_file():
            return {}
        try:
            raw = json.loads(sidecar.read_text())["charts"]
        except Exception:  # noqa: BLE001 - corrupt sidecar = no charts, never a crash
            _LOG.warning("ignoring unreadable charts sidecar")
            return {}
        for payload in raw.values():
            for key in ("datasets", "assumptions", "lineage"):
                payload[key] = tuple(payload.get(key, ()))
        return raw

    def _save_charts(self, charts: dict) -> None:
        import json
        from pathlib import Path

        sidecar = Path(str(self.store.base_dir)) / "charts.json"
        payload = {
            cid: {
                **data,
                "datasets": list(data.get("datasets", ())),
                "assumptions": list(data.get("assumptions", ())),
                "lineage": list(data.get("lineage", ())),
            }
            for cid, data in charts.items()
        }
        sidecar.write_text(json.dumps({"charts": payload}, indent=2))

    # ------------------------------------------------------------------ #
    # Feature 016 — catalog curation. Human-settled meanings live in a
    # per-dataset sidecar and are applied as an OVERLAY wherever a catalog
    # entry is (re)derived — that single choke point is the stickiness
    # guarantee. The agent's blast radius is the synthesis output schema:
    # at most the column's and its own table's description.
    # ------------------------------------------------------------------ #
    def curation(self, name: str) -> dict:
        decisions = self._curation_decisions(name)
        return {
            "columns": decisions.get("columns", {}),
            "table": decisions.get("table"),
        }

    def attach_catalog(self, name: str, entry: object) -> None:
        """Attach a (re)derived catalog entry to a dataset record, applying
        the curation overlay and persisting the sidecar — THE single path
        by which catalog entries reach records (feature 016 stickiness)."""
        import dataclasses

        record = self._records[name]
        curated = self._apply_curation_overlay(name, entry)
        record.summary = dataclasses.replace(record.summary, catalog=curated)
        _save_catalog_sidecar(self.store.base_dir, name, curated)

    def answer_clarification(self, name: str, column: str, answer: str) -> None:
        from analyst.domain.catalog import UnknownCurationError

        if not answer.strip():
            raise ValueError("An answer is required.")
        entry = self._catalog_or_raise(name)
        clarification = next(
            (c for c in entry.clarifications if c.column == column), None
        )
        if clarification is None:
            raise UnknownCurationError(column)
        self._curate(
            name,
            column=column,
            question=clarification.question,
            user_input=answer.strip(),
            kind="answer",
        )

    def suggest_correction(self, name: str, column: str | None, note: str) -> None:
        from analyst.domain.catalog import UnknownCurationError

        if not note.strip():
            raise ValueError("A suggestion is required.")
        entry = self._catalog_or_raise(name)
        if column is not None and all(c.name != column for c in entry.columns):
            raise UnknownCurationError(column)
        self._curate(
            name,
            column=column,
            question=None,
            user_input=note.strip(),
            kind="correction",
        )

    def _catalog_or_raise(self, name: str):  # noqa: ANN202
        from analyst.domain.catalog import UnknownCurationError

        record = self._records.get(name)
        if record is None:
            raise KeyError(name)
        entry = record.summary.catalog
        if entry is None:
            raise UnknownCurationError(name)
        return entry

    def _curate(
        self,
        name: str,
        column: str | None,
        question: str | None,
        user_input: str,
        kind: str,
    ) -> None:
        entry = self._catalog_or_raise(name)
        current_column = next(
            (c.description for c in entry.columns if c.name == column), ""
        )
        if self.curator is not None:
            from analyst.agentic.curation import CurationError
            from analyst.domain.catalog import payload_from_profile

            try:
                result = self.curator.complete(
                    payload_from_profile(name, self._records[name].summary.profile),
                    column,
                    question,
                    user_input,
                    current_column_description=current_column,
                    current_table_description=entry.table_description,
                )
                column_description = result.column_description
                table_description = result.table_description
                pending = False
            except CurationError:
                raise
            except Exception as exc:  # noqa: BLE001 - never a raw 500
                raise CurationError(
                    f"The semantic analysis could not be completed ({exc}). "
                    "Nothing was changed — please try again."
                ) from exc
        else:
            # Offline: the person's words apply verbatim (still sticky),
            # marked for reconciliation when AI is next available.
            pending = True
            if kind == "answer":
                column_description = f"{question} Settled by the user: {user_input}."
                table_description = None
            elif column is not None:
                column_description, table_description = user_input, None
            else:
                column_description, table_description = None, user_input
        decisions = self._curation_decisions(name)
        stamp = {"kind": kind, "input": user_input, "pending_reconciliation": pending}
        if column is not None and column_description:
            decisions.setdefault("columns", {})[column] = {
                **stamp,
                "description": column_description,
            }
        if table_description:
            decisions["table"] = {**stamp, "description": table_description}
        if kind == "answer" and question:
            decisions.setdefault("answered", []).append(question)
        self._save_curation(name, decisions)
        self.attach_catalog(name, entry)

    def _apply_curation_overlay(self, name: str, entry):  # noqa: ANN001, ANN202
        import dataclasses

        decisions = self._curation_decisions(name)
        if not decisions:
            return entry
        curated_columns = decisions.get("columns", {})
        answered = set(decisions.get("answered", []))
        columns = tuple(
            dataclasses.replace(
                c, description=str(curated_columns[c.name]["description"])
            )
            if c.name in curated_columns
            else c
            for c in entry.columns
        )
        table = entry.table_description
        if decisions.get("table"):
            table = str(decisions["table"]["description"])
        clarifications = tuple(
            c
            for c in entry.clarifications
            if c.question not in answered and c.column not in curated_columns
        )
        return dataclasses.replace(
            entry,
            columns=columns,
            table_description=table,
            clarifications=clarifications,
        )

    def _curation_decisions(self, name: str) -> dict:
        import json
        from pathlib import Path

        sidecar = Path(str(self.store.base_dir)) / f"{name}.curation.json"
        if not sidecar.is_file():
            return {}
        try:
            return dict(json.loads(sidecar.read_text()))
        except Exception:  # noqa: BLE001 - corrupt sidecar = no curation, never a crash
            _LOG.warning("ignoring unreadable curation sidecar for %r", name)
            return {}

    def _save_curation(self, name: str, decisions: dict) -> None:
        import json
        from pathlib import Path

        sidecar = Path(str(self.store.base_dir)) / f"{name}.curation.json"
        sidecar.write_text(json.dumps(decisions, indent=2))

    # ------------------------------------------------------------------ #
    # Feature 015 — dashboards. A widget is a saved-chart shape + source;
    # filters substitute the /*FILTERS*/ marker BEFORE aggregation and the
    # final SQL is re-guarded on every run. Widgets fail alone: one broken
    # query yields a per-widget error, never a dead dashboard.
    # ------------------------------------------------------------------ #
    def dashboards(self) -> list:
        from analyst.domain.dashboards import (
            Dashboard,
            DashboardFilter,
            DashboardWidget,
        )

        out = []
        for did, data in self._load_dashboards().items():
            out.append(
                Dashboard(
                    dashboard_id=did,
                    name=data["name"],
                    widgets=tuple(
                        DashboardWidget(**w) for w in data.get("widgets", [])
                    ),
                    filters=tuple(
                        DashboardFilter(**f) for f in data.get("filters", [])
                    ),
                )
            )
        return out

    def put_dashboard(self, dashboard: Any) -> None:
        import dataclasses

        from analyst.engine.dashboards import validate_widget_sql

        for widget in dashboard.widgets:  # reject-whole (AC-13)
            validate_widget_sql(widget.sql)
            problems = self.store.validation_problems(
                widget.sql.replace("/*FILTERS*/", "")
            )
            if problems:
                raise ValueError(f"Widget '{widget.title}': {problems[0]}")
        data = self._load_dashboards()
        data[dashboard.dashboard_id] = {
            "name": dashboard.name,
            "widgets": [dataclasses.asdict(w) for w in dashboard.widgets],
            "filters": [dataclasses.asdict(f) for f in dashboard.filters],
        }
        self._save_dashboards(data)

    def run_dashboard(self, dashboard_id: str, filters: list) -> dict:
        from analyst.api.qa import shape_answer
        from analyst.domain.query import PlanAction, QueryPlan
        from analyst.engine.dashboards import apply_filters
        from analyst.engine.query import run_select

        dashboard = self._require_dashboard(dashboard_id)
        results: dict = {"dashboard": dashboard, "widgets": {}}
        for widget in dashboard.widgets:
            applicable, skipped = self._split_filters(widget.source, filters)
            entry: dict = {"answer": None, "error": None, "unaffected_by": skipped}
            try:
                sql = apply_filters(widget.sql, applicable)
                problems = self.store.validation_problems(sql)
                if problems:
                    raise ValueError(problems[0])
                plan = QueryPlan(
                    action=PlanAction.ANSWER,
                    sql=sql,
                    title=widget.title,
                    assumptions=widget.assumptions,
                    lineage=widget.lineage or (f"source: {widget.source}",),
                )
                result = run_select(self.store, sql)
                # Dashboards chart every row (the workbench scrolls past ~12
                # bars); Q&A keeps its tighter default.
                answer = shape_answer(plan, result, max_chart_rows=200)
                if widget.chart_type in {"bar", "line"} and answer.chart_data:
                    answer.chart_type = widget.chart_type
                entry["answer"] = answer
            except Exception as exc:  # noqa: BLE001 - widgets fail ALONE
                entry["error"] = f"This widget's data is gone or invalid: {exc}"
            results["widgets"][widget.widget_id] = entry
        return results

    def drill_dashboard(
        self, dashboard_id: str, widget_id: str, filters: list
    ) -> object:
        from analyst.api.qa import shape_answer
        from analyst.domain.dashboards import UnknownDashboardError
        from analyst.domain.query import PlanAction, QueryPlan
        from analyst.engine.dashboards import apply_filters
        from analyst.engine.query import run_select
        from analyst.engine.store import _quote_ident

        dashboard = self._require_dashboard(dashboard_id)
        widget = next((w for w in dashboard.widgets if w.widget_id == widget_id), None)
        if widget is None:
            raise UnknownDashboardError(widget_id)
        applicable, _ = self._split_filters(widget.source, filters)
        sql = apply_filters(
            f"SELECT * FROM {_quote_ident(widget.source)} WHERE /*FILTERS*/ 1=1",
            applicable,
        )
        plan = QueryPlan(
            action=PlanAction.ANSWER,
            sql=sql,
            title=f"Rows behind: {widget.title}",
            lineage=(f"source: {widget.source}",),
        )
        return shape_answer(plan, run_select(self.store, sql))

    def delete_dashboard(self, dashboard_id: str) -> None:
        data = self._load_dashboards()
        self._require_dashboard(dashboard_id)
        del data[dashboard_id]
        self._save_dashboards(data)

    def remove_widget(self, dashboard_id: str, widget_id: str) -> None:
        from analyst.domain.dashboards import UnknownDashboardError

        data = self._load_dashboards()
        self._require_dashboard(dashboard_id)
        widgets = data[dashboard_id].get("widgets", [])
        if all(w["widget_id"] != widget_id for w in widgets):
            raise UnknownDashboardError(widget_id)
        data[dashboard_id]["widgets"] = [
            w for w in widgets if w["widget_id"] != widget_id
        ]
        self._save_dashboards(data)

    def _split_filters(self, source: str, filters: list) -> tuple[list, list]:
        """(applicable, unaffected-column-names) for one widget's source."""
        try:
            columns = {name for name, _ in self.store.schema(source)}
        except Exception:  # noqa: BLE001 - source gone: nothing applies
            columns = set()
        applicable = [(c, v) for c, v in filters if c in columns]
        skipped = [c for c, _ in filters if c not in columns]
        return applicable, skipped

    def _require_dashboard(self, dashboard_id: str):  # noqa: ANN202
        from analyst.domain.dashboards import UnknownDashboardError

        data = self._load_dashboards()
        if dashboard_id not in data:
            raise UnknownDashboardError(dashboard_id)
        return next(d for d in self.dashboards() if d.dashboard_id == dashboard_id)

    def _load_dashboards(self) -> dict:
        import json
        from pathlib import Path

        sidecar = Path(str(self.store.base_dir)) / "dashboards.json"
        if not sidecar.is_file():
            return {}
        try:
            return dict(json.loads(sidecar.read_text())["dashboards"])
        except Exception:  # noqa: BLE001
            _LOG.warning("ignoring unreadable dashboards sidecar")
            return {}

    def _save_dashboards(self, data: dict) -> None:
        import json
        from pathlib import Path

        sidecar = Path(str(self.store.base_dir)) / "dashboards.json"
        sidecar.write_text(json.dumps({"dashboards": data}, indent=2))

    def create_dashboard(self, request: str) -> dict:
        result = self._assemble(request, current_spec=None)
        if result.clarification is not None:
            return {"clarification": result.clarification, "dashboard": None}
        dashboard = self._dashboard_from_spec(result, dashboard_id=None)
        self.put_dashboard(dashboard)  # reject-whole on any invalid widget
        return {"clarification": None, "dashboard": dashboard}

    def edit_dashboard(self, dashboard_id: str, request: str) -> dict:
        import json as _json

        current = self._require_dashboard(dashboard_id)
        spec = _json.dumps(self._load_dashboards()[dashboard_id], indent=1)
        result = self._assemble(request, current_spec=spec)
        if result.clarification is not None:
            return {"clarification": result.clarification, "dashboard": None}
        dashboard = self._dashboard_from_spec(
            result, dashboard_id=dashboard_id, fallback_name=current.name
        )
        self.put_dashboard(dashboard)
        return {"clarification": None, "dashboard": dashboard}

    def _assemble(self, request: str, current_spec: str | None):  # noqa: ANN202
        from analyst.agentic.dashboards import DashboardAssemblyError
        from analyst.domain.query import query_table_from_summary

        if self.assembler is None:
            raise DashboardAssemblyError(
                "Dashboard authoring needs the AI features — set "
                "ANTHROPIC_API_KEY / CLAUDE_CODE_OAUTH_TOKEN and "
                "ANALYST_CATALOG=live. Existing dashboards keep working."
            )
        tables = [
            query_table_from_summary(record.summary)
            for record in self._records.values()
            if not record.federated or record.db_queryable
        ]
        return self.assembler.assemble(request, tables, current_spec)

    def _dashboard_from_spec(
        self,
        result,  # noqa: ANN001 - AssemblyResult
        dashboard_id: str | None,
        fallback_name: str = "Dashboard",
    ):  # noqa: ANN202
        from analyst.domain.charts import chart_id_for
        from analyst.domain.dashboards import (
            Dashboard,
            DashboardFilter,
            DashboardWidget,
        )

        name = result.name or fallback_name
        if dashboard_id is None:
            dashboard_id = chart_id_for(name, set(self._load_dashboards()))
        taken: set[str] = set()
        widgets = []
        for spec in result.widgets:
            widget_id = chart_id_for(spec.title, taken)
            taken.add(widget_id)
            widgets.append(
                DashboardWidget(
                    widget_id=widget_id,
                    question=spec.question,
                    sql=spec.sql,
                    chart_type=spec.chart_type,
                    title=spec.title,
                    source=spec.source,
                )
            )
        return Dashboard(
            dashboard_id=dashboard_id,
            name=name,
            widgets=tuple(widgets),
            filters=tuple(
                DashboardFilter(column=f.column, label=f.label) for f in result.filters
            ),
        )


def _normalization_sidecar(base_dir: object, name: str):  # noqa: ANN001
    from pathlib import Path

    return Path(str(base_dir)) / f"{name}.normalization.json"


def _catalog_sidecar(base_dir: object, name: str):  # noqa: ANN001
    from pathlib import Path

    return Path(str(base_dir)) / f"{name}.catalog.json"


def _profile_to_dict(profile) -> dict:  # noqa: ANN001
    """JSON-safe DatasetProfile (feature 011: shown while a remembered
    connection is unreachable). Enum types become their values; scalars that
    JSON can't carry become strings (display-only until reconnect)."""
    import dataclasses
    import json

    data = dataclasses.asdict(profile)
    for col in data["columns"]:
        col["inferred_type"] = col["inferred_type"].value
        if col.get("dominant_type") is not None:
            col["dominant_type"] = col["dominant_type"].value
    return json.loads(json.dumps(data, default=str))


def _profile_from_dict(data: dict):  # noqa: ANN001
    from analyst.domain.profile import ColumnProfile, DatasetProfile, DistributionBin
    from analyst.domain.types import ColumnType

    columns = tuple(
        ColumnProfile(
            name=c["name"],
            inferred_type=ColumnType(c["inferred_type"]),
            null_count=c["null_count"],
            distinct_count=c["distinct_count"],
            samples=tuple(c.get("samples", ())),
            minimum=c.get("minimum"),
            maximum=c.get("maximum"),
            quantiles=tuple(c.get("quantiles", ())),
            distribution=tuple(DistributionBin(**b) for b in c.get("distribution", ())),
            is_mixed=c.get("is_mixed", False),
            dominant_type=(
                ColumnType(c["dominant_type"]) if c.get("dominant_type") else None
            ),
            off_type_examples=tuple(c.get("off_type_examples", ())),
            is_nested=c.get("is_nested", False),
        )
        for c in data["columns"]
    )
    return DatasetProfile(
        row_count=data["row_count"],
        columns=columns,
        encoding=data.get("encoding"),
        synthesized_headers=data.get("synthesized_headers", False),
        had_duplicate_columns=data.get("had_duplicate_columns", False),
    )


def _schema_fingerprint(profile: object) -> str:
    """A stable schema id (feature 010, AC-7): sorted column name:type pairs.
    A table whose fingerprint changed while the service was down is
    re-catalogued on reconnect; an unchanged one reuses its persisted entry."""
    columns = getattr(profile, "columns", ())
    return "|".join(sorted(f"{c.name}:{c.inferred_type.value}" for c in columns))


def _save_catalog_sidecar(
    base_dir: object,
    name: str,
    catalog: object,
    fingerprint: str | None = None,
    profile: object | None = None,
) -> None:
    """Persist a catalog entry so it survives a restart (HIGH H2 + cataloguer).
    ``fingerprint`` (feature 010) and ``profile`` (feature 011: display while
    unreachable) ride along for connected-DB tables; loaders that don't know
    the keys simply ignore them."""
    import dataclasses
    import json

    if not dataclasses.is_dataclass(catalog) or isinstance(catalog, type):
        return
    payload = dataclasses.asdict(catalog)
    if fingerprint is not None:
        payload["schema_fingerprint"] = fingerprint
    if profile is not None:
        payload["profile"] = _profile_to_dict(profile)
    _catalog_sidecar(base_dir, name).write_text(json.dumps(payload), encoding="utf-8")


def _load_catalog_sidecar(base_dir: object, name: str):  # noqa: ANN001
    loaded = _load_catalog_sidecar_with_fingerprint(base_dir, name)
    return loaded[0] if loaded is not None else None


def _load_catalog_sidecar_with_fingerprint(base_dir: object, name: str):  # noqa: ANN001
    path = _catalog_sidecar(base_dir, name)
    if not path.exists():
        return None
    import json

    from analyst.domain.catalog import (
        CatalogEntry,
        Clarification,
        ColumnDescription,
    )
    from analyst.domain.relationships import Relationship

    data = json.loads(path.read_text(encoding="utf-8"))
    entry = CatalogEntry(
        table_description=data["table_description"],
        columns=tuple(ColumnDescription(**c) for c in data["columns"]),
        clarifications=tuple(
            Clarification(
                question=c["question"],
                options=tuple(c["options"]),
                column=c.get("column"),
            )
            for c in data["clarifications"]
        ),
        relationships=tuple(Relationship(**r) for r in data.get("relationships", [])),
    )
    profile = _profile_from_dict(data["profile"]) if data.get("profile") else None
    return entry, data.get("schema_fingerprint"), profile


def _safe_upload_name(file_name: str) -> str:
    """Basename-only upload name (SECURITY C1) — strips any directory component
    (`../`, absolute paths, Windows separators) so a crafted filename can never
    escape the temp directory it's written into."""
    from pathlib import PurePosixPath, PureWindowsPath

    raw = (file_name or "").strip()
    # Handle both separator styles regardless of host OS.
    base = PureWindowsPath(PurePosixPath(raw).name).name.strip()
    return base or "upload.csv"
